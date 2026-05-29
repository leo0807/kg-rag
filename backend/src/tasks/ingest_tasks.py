"""F117: ingest_document Celery task"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from ..celery_app import celery_app
from ..services.parsing.parser import parse
from ..services.graph.neo4j_writer import write_document, write_document_incremental
from ..routers.docs.ingest_helpers import run_image_analysis

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")


def _make_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "aviation123"),
        ),
    )


@celery_app.task(bind=True, name="ingest_document")
def ingest_document(self, tmp_path_str: str, incremental: bool = True) -> dict:
    """Ingest a document into the knowledge graph.

    Returns: {"status": "done" | "skipped", "doc_id": str, "sections": int}
    """
    driver = _make_driver()
    try:
        return asyncio.run(_run(self, Path(tmp_path_str), driver, incremental))
    finally:
        driver.close()


async def _run(task, tmp_path: Path, driver, incremental: bool) -> dict:
    def _progress(step: str) -> None:
        task.update_state(state="PROGRESS", meta={"step": step})

    doc = None
    try:
        _progress("parsing")
        doc = await asyncio.to_thread(parse, tmp_path)

        stable_path = UPLOAD_DIR / f"{doc.doc_id}{tmp_path.suffix.lower()}"
        if tmp_path != stable_path:
            tmp_path.replace(stable_path)
            tmp_path = stable_path

        _progress("checking")
        with driver.session() as session:
            rec = session.run(
                "MATCH (d:Document {name: $doc_id}) WHERE d.title IS NOT NULL RETURN count(d) AS cnt",
                doc_id=doc.doc_id,
            ).single()
        if rec and rec["cnt"] > 0:
            if incremental:
                _progress("writing")
                inc_stats = await asyncio.to_thread(write_document_incremental, doc)
                return {"status": "done", "doc_id": doc.doc_id,
                        "sections": doc.total_sections, "incremental_stats": inc_stats}
            return {"status": "skipped", "doc_id": doc.doc_id, "sections": doc.total_sections}

        _progress("writing")
        await asyncio.to_thread(write_document, doc)

        if tmp_path.suffix.lower() in (".docx", ".doc"):
            _progress("converting")
            try:
                from ..routers.docs.documents import _find_soffice, PREVIEW_DIR as _PREVIEW_DIR
                import subprocess as _sp
                _soffice = _find_soffice()
                if _soffice:
                    _pdf_out = _PREVIEW_DIR / f"{doc.doc_id}.pdf"
                    if not _pdf_out.exists():
                        await asyncio.to_thread(
                            lambda: _sp.run(
                                [_soffice, "--headless", "--convert-to", "pdf",
                                 "--outdir", str(_PREVIEW_DIR), str(tmp_path)],
                                check=True, stdout=_sp.PIPE, stderr=_sp.PIPE,
                            )
                        )
            except Exception as e:
                logger.warning("DOCX→PDF 预转换跳过 doc_id=%s: %s", doc.doc_id, e)

        section_dicts = [
            {"chunk_id": s.chunk_id, "title": s.title, "content": s.content}
            for s in doc.sections
        ]

        _progress("entities")
        try:
            from ..services.graph.entity_extractor import (
                extract_entities_from_sections,
                extract_constraints_from_sections,
            )
            from ..services.graph.entity_writer import write_entities, write_constraints

            entity_data = await asyncio.to_thread(extract_entities_from_sections, section_dicts)
            await asyncio.to_thread(write_entities, driver, doc.doc_id, entity_data)

            _progress("constraints")
            constraint_data = await asyncio.to_thread(extract_constraints_from_sections, section_dicts)
            await asyncio.to_thread(write_constraints, driver, doc.doc_id, constraint_data)
        except Exception as e:
            logger.warning("实体/约束提取失败（不影响主流程）: %s", e)

        _pdf_for_extraction = str(doc.pdf_path) if doc.pdf_path and doc.pdf_path.exists() else str(tmp_path)

        _progress("tables")
        try:
            from ..services.tables.table_extractor import extract_all_tables, is_available as tables_available
            from ..services.graph.entity_writer import write_constraints as _wc
            if tables_available():
                table_cons = await asyncio.to_thread(
                    extract_all_tables, _pdf_for_extraction, doc.doc_id, section_dicts
                )
                if table_cons:
                    await asyncio.to_thread(_wc, driver, doc.doc_id, table_cons)
        except Exception as e:
            logger.warning("表格提取失败（不影响主流程）: %s", e)

        _progress("images")
        await run_image_analysis(driver, doc.doc_id, _pdf_for_extraction)

        _progress("storing")
        try:
            from ..core.storage import upload_file as _upload_file, BUCKET_RAW_DOCUMENTS
            minio_key = f"{doc.doc_id}{tmp_path.suffix.lower()}"
            await asyncio.to_thread(_upload_file, BUCKET_RAW_DOCUMENTS, minio_key, tmp_path)
            with driver.session() as _s:
                _s.run(
                    "MATCH (d:Document {name: $doc_id}) SET d.storage_key = $key",
                    doc_id=doc.doc_id, key=minio_key,
                )
            tmp_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("MinIO 上传失败（本地文件保留作为回退）: %s", e)
        finally:
            if doc and doc.pdf_path and doc.pdf_path != tmp_path:
                doc.pdf_path.unlink(missing_ok=True)

        logger.info("ingest 完成 doc_id=%s", doc.doc_id)
        return {"status": "done", "doc_id": doc.doc_id, "sections": doc.total_sections}

    except Exception as e:
        logger.exception("ingest task 失败: %s", e)
        raise  # let Celery mark it FAILURE
