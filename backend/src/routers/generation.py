"""
规范生成任务接口 — 任务管理（A2）+ 生成控制（A4）+ 编辑导出（A6）

POST   /api/generation/tasks                           — 创建任务
GET    /api/generation/tasks                           — 任务列表
GET    /api/generation/tasks/{task_id}                 — 任务详情
DELETE /api/generation/tasks/{task_id}                 — 删除任务
POST   /api/generation/tasks/{task_id}/upload-test-data — 上传试验数据
POST   /api/generation/tasks/{task_id}/start           — 启动生成
GET    /api/generation/tasks/{task_id}/stream          — SSE 进度推送
GET    /api/generation/tasks/{task_id}/draft           — 获取草稿
PUT    /api/generation/tasks/{task_id}/section/{num}   — 更新章节
POST   /api/generation/tasks/{task_id}/regenerate/{num}— 重新生成章节
POST   /api/generation/tasks/{task_id}/finalize        — 定稿
POST   /api/generation/tasks/{task_id}/export          — 导出
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.gen_models import GenerationTask
from ..db.models import User
from ..db.session import get_db
from ..services.generation.input_models import GenerationInput, parse_excel_test_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/generation", tags=["generation"])


# ── helpers ──────────────────────────────────────────────────────────────────

def _task_dict(t: GenerationTask) -> dict:
    return {
        "id":                t.id,
        "task_name":         t.task_name,
        "spec_type":         t.spec_type,
        "template_id":       t.template_id,
        "status":            t.status,
        "progress":          t.progress,
        "current_step":      t.current_step,
        "inputs":            t.inputs,
        "result_sections":   t.result_sections,
        "validation_report": t.validation_report,
        "error":             t.error,
        "created_at":        t.created_at.isoformat() if t.created_at else None,
        "completed_at":      t.completed_at,
    }


async def _get_task_or_404(task_id: str, db: AsyncSession) -> GenerationTask:
    result = await db.execute(select(GenerationTask).where(GenerationTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


# ── A2: Task CRUD ─────────────────────────────────────────────────────────────

@router.post("/tasks", status_code=201)
async def create_task(
    body: GenerationInput,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = GenerationTask(
        task_name=body.spec_name,
        spec_type=body.spec_type,
        template_id=body.template_id,
        inputs=body.model_dump(),
        status="pending",
        user_id=user.id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _task_dict(task)


@router.get("/tasks")
async def list_tasks(
    status: str | None = None,
    limit:  int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(GenerationTask).where(GenerationTask.user_id == user.id)
    if status:
        stmt = stmt.where(GenerationTask.status == status)
    stmt = stmt.order_by(GenerationTask.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    items = [_task_dict(t) for t in result.scalars().all()]
    return {"items": items, "total": len(items)}


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return _task_dict(await _get_task_or_404(task_id, db))


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    await db.delete(task)
    await db.commit()


@router.post("/tasks/{task_id}/upload-test-data")
async def upload_test_data(
    task_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    if task.status not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail="only pending/failed tasks can be updated")

    content = await file.read()
    parsed = parse_excel_test_data(content, file.filename or "data.xlsx")

    inputs = dict(task.inputs or {})
    inputs["test_data"] = parsed.model_dump()
    task.inputs = inputs
    await db.commit()
    return {"rows": len(parsed.rows), "parameters": parsed.summary.get("parameters", [])}


# ── A4: Start generation + SSE ────────────────────────────────────────────────

@router.post("/tasks/{task_id}/start")
async def start_generation(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    if task.status == "running":
        raise HTTPException(status_code=409, detail="task already running")
    task.status = "running"
    task.progress = 0
    task.error = ""
    await db.commit()

    from ..services.generation.workflow import SpecGenerationWorkflow
    asyncio.create_task(SpecGenerationWorkflow().run(task_id))
    return {"status": "started", "task_id": task_id}


@router.get("/tasks/{task_id}/stream")
async def stream_progress(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """SSE 推送生成进度。每2秒轮询一次数据库，直到完成或失败。"""

    async def _event_gen():
        for _ in range(300):  # 最多等 10 分钟
            await asyncio.sleep(2)
            result = await db.execute(select(GenerationTask).where(GenerationTask.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                yield f"event: error\ndata: task not found\n\n"
                return
            payload = json.dumps({
                "progress":     task.progress,
                "current_step": task.current_step,
                "status":       task.status,
            })
            yield f"event: progress\ndata: {payload}\n\n"
            if task.status in ("done", "failed"):
                yield f"event: done\ndata: {json.dumps({'status': task.status})}\n\n"
                return

    return StreamingResponse(_event_gen(), media_type="text/event-stream")


# ── A6: Draft editing + export ────────────────────────────────────────────────

@router.get("/tasks/{task_id}/draft")
async def get_draft(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    return {
        "task_id":           task_id,
        "task_name":         task.task_name,
        "status":            task.status,
        "sections":          task.result_sections or {},
        "validation_report": task.validation_report,
    }


@router.put("/tasks/{task_id}/section/{section_num}")
async def update_section(
    task_id:     str,
    section_num: str,
    body:        dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    sections = dict(task.result_sections or {})
    sections[section_num] = body.get("content", "")
    task.result_sections = sections
    await db.commit()
    return {"section": section_num, "updated": True}


@router.post("/tasks/{task_id}/regenerate/{section_num}")
async def regenerate_section(
    task_id:     str,
    section_num: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    if task.status == "running":
        raise HTTPException(status_code=409, detail="generation already in progress")

    from ..services.generation.workflow import SpecGenerationWorkflow
    asyncio.create_task(
        SpecGenerationWorkflow().regenerate_section(task_id, section_num)
    )
    return {"status": "regenerating", "section": section_num}


@router.post("/tasks/{task_id}/finalize")
async def finalize_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    task.status = "finalized"
    task.completed_at = datetime.utcnow().isoformat()
    await db.commit()
    return {"status": "finalized"}


@router.post("/tasks/{task_id}/export")
async def export_draft(
    task_id: str,
    fmt:     str = "docx",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    task = await _get_task_or_404(task_id, db)
    if not task.result_sections:
        raise HTTPException(status_code=422, detail="no draft content to export")

    from ..services.generation.doc_exporter import export_to_docx, export_to_markdown
    sections = task.result_sections or {}

    from urllib.parse import quote
    safe_name = quote(task.task_name, safe="")

    if fmt == "markdown":
        content = export_to_markdown(task.task_name, sections)
        return StreamingResponse(
            iter([content.encode("utf-8")]),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.md"},
        )

    # default: docx
    import io
    buf = io.BytesIO()
    export_to_docx(task.task_name, sections, buf)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.read()]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.docx"},
    )
