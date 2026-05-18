from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from neo4j import Driver

from ...auth.deps import get_admin_user as _get_admin_user
from ...core.database import get_driver
from ...services.graph.neo4j_writer import write_document, write_document_incremental
from ...services.parsing.parser import parse
from ...services.security.upload_validator import DOCUMENT_TYPES, validate_upload
from .ingest_helpers import run_image_analysis

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "images").mkdir(exist_ok=True)

_ingest_tasks: dict[str, dict] = {}
INGEST_SEMAPHORE = asyncio.Semaphore(2)


def _task_update(task_id: str, **kw: object) -> None:
    if task_id in _ingest_tasks:
        _ingest_tasks[task_id].update(kw)


def _cleanup_old_tasks() -> None:
    cutoff = datetime.utcnow() - timedelta(hours=2)
    stale = [k for k, v in _ingest_tasks.items()
             if v.get("created_at", datetime.utcnow()) < cutoff]
    for k in stale:
        _ingest_tasks.pop(k, None)


async def _run_ingest_bg(task_id: str, tmp_path: Path, driver: Driver, incremental: bool = True) -> None:
    doc = None
    section_dicts: list[dict] = []
    try:
        async with INGEST_SEMAPHORE:
            _task_update(task_id, step="parsing")
            doc = await asyncio.to_thread(parse, tmp_path)

            stable_path = UPLOAD_DIR / f"{doc.doc_id}{tmp_path.suffix.lower()}"
            if tmp_path != stable_path:
                tmp_path.replace(stable_path)
                tmp_path = stable_path

            _task_update(task_id, step="checking")
            with driver.session() as session:
                rec = session.run(
                    "MATCH (d:Document {name: $doc_id}) WHERE d.title IS NOT NULL RETURN count(d) AS cnt",
                    doc_id=doc.doc_id,
                ).single()
            if rec and rec["cnt"] > 0:
                if incremental:
                    _task_update(task_id, step="writing")
                    inc_stats = await asyncio.to_thread(write_document_incremental, doc)
                    _task_update(task_id, status="done", doc_id=doc.doc_id,
                                 sections=doc.total_sections, incremental_stats=inc_stats)
                else:
                    _task_update(task_id, status="skipped", doc_id=doc.doc_id, sections=doc.total_sections)
                return

            _task_update(task_id, step="writing")
            await asyncio.to_thread(write_document, doc)

        if tmp_path.suffix.lower() in (".docx", ".doc"):
            _task_update(task_id, step="converting")
            try:
                from .documents import _find_soffice, PREVIEW_DIR as _PREVIEW_DIR
                _soffice = _find_soffice()
                if _soffice:
                    import subprocess as _sp
                    _pdf_out = _PREVIEW_DIR / f"{doc.doc_id}.pdf"
                    if not _pdf_out.exists():
                        await asyncio.to_thread(
                            lambda: _sp.run(
                                [_soffice, "--headless", "--convert-to", "pdf",
                                 "--outdir", str(_PREVIEW_DIR), str(tmp_path)],
                                check=True, stdout=_sp.PIPE, stderr=_sp.PIPE,
                            )
                        )
                        logger.info("DOCX→PDF 预转换完成 doc_id=%s", doc.doc_id)
            except Exception as _ce:
                logger.warning("DOCX→PDF 预转换跳过 doc_id=%s: %s", doc.doc_id, _ce)

        section_dicts = [
            {"chunk_id": s.chunk_id, "title": s.title, "content": s.content}
            for s in doc.sections
        ]

        _task_update(task_id, step="entities")
        try:
            from ...services.graph.entity_extractor import (
                extract_entities_from_sections,
                extract_constraints_from_sections,
            )
            from ...services.graph.entity_writer import write_entities, write_constraints

            entity_data = await asyncio.to_thread(extract_entities_from_sections, section_dicts)
            await asyncio.to_thread(write_entities, driver, doc.doc_id, entity_data)

            _task_update(task_id, step="constraints")
            constraint_data = await asyncio.to_thread(extract_constraints_from_sections, section_dicts)
            await asyncio.to_thread(write_constraints, driver, doc.doc_id, constraint_data)
        except Exception as e:
            logger.warning("实体/约束提取失败（不影响主流程）: %s", e)

        _pdf_for_extraction = str(doc.pdf_path) if doc.pdf_path and doc.pdf_path.exists() else str(tmp_path)

        _task_update(task_id, step="tables")
        try:
            from ...services.tables.table_extractor import extract_all_tables, is_available as tables_available
            from ...services.graph.entity_writer import write_constraints as _wc
            if tables_available():
                table_cons = await asyncio.to_thread(
                    extract_all_tables, _pdf_for_extraction, doc.doc_id, section_dicts
                )
                if table_cons:
                    await asyncio.to_thread(_wc, driver, doc.doc_id, table_cons)
                    logger.info("表格约束写入 %d 条", len(table_cons))
        except Exception as e:
            logger.warning("表格提取失败（不影响主流程）: %s", e)

        _task_update(task_id, step="images")
        await run_image_analysis(driver, doc.doc_id, _pdf_for_extraction)

        _task_update(task_id, step="storing")
        try:
            from ...core.storage import upload_file as _upload_file, BUCKET_RAW_DOCUMENTS
            minio_key = f"{doc.doc_id}{tmp_path.suffix.lower()}"
            await asyncio.to_thread(_upload_file, BUCKET_RAW_DOCUMENTS, minio_key, tmp_path)
            with driver.session() as _s:
                _s.run(
                    "MATCH (d:Document {name: $doc_id}) SET d.storage_key = $key",
                    doc_id=doc.doc_id, key=minio_key,
                )
            tmp_path.unlink(missing_ok=True)
            logger.info("文件已上传到 MinIO: %s/%s", BUCKET_RAW_DOCUMENTS, minio_key)
        except Exception as _me:
            logger.warning("MinIO 上传失败（本地文件保留作为回退）: %s", _me)
        finally:
            if doc and doc.pdf_path and doc.pdf_path != tmp_path:
                doc.pdf_path.unlink(missing_ok=True)

        _task_update(task_id, status="done", doc_id=doc.doc_id, sections=doc.total_sections)
        logger.info("ingest 完成 task_id=%s doc_id=%s", task_id, doc.doc_id)

    except Exception as e:
        logger.exception("ingest 后台任务失败 task_id=%s: %s", task_id, e)
        _task_update(task_id, status="error", error=str(e))


@router.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    content  = await validate_upload(file)
    tmp_path = UPLOAD_DIR / (file.filename or "preview.pdf")
    tmp_path.write_bytes(content)
    try:
        return parse(tmp_path)
    except Exception as e:
        logger.warning(
            "PDF parse failed: filename=%r error=%s: %s",
            file.filename,
            type(e).__name__,
            e,
        )
        raise HTTPException(
            status_code=422,
            detail=f"无法解析 PDF：{type(e).__name__}",
        )


@router.post("/api/ingest")
async def ingest(
    file:        UploadFile = File(...),
    incremental: bool       = Form(True),
    driver:      Driver     = Depends(get_driver),
    _:           object     = Depends(_get_admin_user),
):
    """接收文件并立即返回 task_id，实际入库在后台执行。"""
    _cleanup_old_tasks()

    task_id  = uuid.uuid4().hex[:12]
    tmp_path = UPLOAD_DIR / f"{task_id}_{file.filename or 'upload'}"
    content = await validate_upload(file, allowed_types=DOCUMENT_TYPES)
    tmp_path.write_bytes(content)

    file_size = tmp_path.stat().st_size

    _ingest_tasks[task_id] = {
        "status": "running", "step": "queued", "doc_id": None,
        "sections": 0, "error": None, "incremental_stats": None, "created_at": datetime.utcnow(),
    }
    asyncio.create_task(_run_ingest_bg(task_id, tmp_path, driver, incremental))
    return {"task_id": task_id, "status": "running"}


@router.get("/api/ingest/status/{task_id}")
async def ingest_status(task_id: str, _: object = Depends(_get_admin_user)):
    """轮询入库任务状态。status: running | done | skipped | error"""
    task = _ingest_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {k: v for k, v in task.items() if k != "created_at"}


def list_ingest_tasks(limit: int = 20) -> list[dict]:
    rows: list[dict] = []
    for task_id, task in _ingest_tasks.items():
        rows.append({
            "task_id":  task_id,
            "status":   task.get("status", "unknown"),
            "step":     task.get("step", ""),
            "doc_id":   task.get("doc_id"),
            "sections": task.get("sections", 0),
            "error":    task.get("error"),
            "created_at": (
                task["created_at"].isoformat()
                if isinstance(task.get("created_at"), datetime)
                else str(task.get("created_at") or "")
            ),
        })
    rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return rows[:max(limit, 1)]
