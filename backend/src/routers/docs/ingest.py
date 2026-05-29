from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...auth.deps import get_admin_user as _get_admin_user
from ...services.security.upload_validator import DOCUMENT_TYPES, validate_upload
from .ingest_helpers import run_image_analysis  # noqa: F401 — re-exported for other modules

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "images").mkdir(exist_ok=True)

# Ring buffer of recently submitted Celery task IDs (task_id, submitted_at)
_recent_task_ids: deque[tuple[str, str]] = deque(maxlen=100)

_STATUS_MAP = {
    "PENDING":  "queued",
    "STARTED":  "running",
    "PROGRESS": "running",
    "SUCCESS":  "done",
    "FAILURE":  "failed",
    "REVOKED":  "cancelled",
}


@router.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    from ...services.parsing.parser import parse

    content  = await validate_upload(file)
    tmp_path = UPLOAD_DIR / (file.filename or "preview.pdf")
    tmp_path.write_bytes(content)
    try:
        return parse(tmp_path)
    except Exception as e:
        logger.warning("PDF parse failed: filename=%r error=%s: %s", file.filename, type(e).__name__, e)
        raise HTTPException(status_code=422, detail=f"无法解析 PDF：{type(e).__name__}")


@router.post("/api/ingest")
async def ingest(
    file:        UploadFile = File(...),
    incremental: bool       = Form(True),
    _:           object     = Depends(_get_admin_user),
):
    """接收文件并立即返回 task_id，实际入库由 Celery worker 执行。"""
    from ...tasks.ingest_tasks import ingest_document

    tmp_path = UPLOAD_DIR / (file.filename or "upload")
    content = await validate_upload(file, allowed_types=DOCUMENT_TYPES)
    tmp_path.write_bytes(content)

    result = ingest_document.delay(str(tmp_path), incremental)
    _recent_task_ids.appendleft((result.id, _now_iso()))
    return {"task_id": result.id, "status": "queued"}


@router.get("/api/ingest/status/{task_id}")
async def ingest_status(task_id: str, _: object = Depends(_get_admin_user)):
    """轮询入库任务状态。status: queued | running | done | failed | cancelled"""
    from ...celery_app import celery_app

    ar = celery_app.AsyncResult(task_id)
    info = ar.info if isinstance(ar.info, dict) else {}
    return {
        "task_id":  task_id,
        "status":   _STATUS_MAP.get(ar.state, "unknown"),
        "step":     info.get("step"),
        "doc_id":   info.get("doc_id") if ar.successful() else None,
        "sections": info.get("sections") if ar.successful() else None,
        "error":    str(ar.info) if ar.failed() else None,
    }


def list_ingest_tasks(limit: int = 20) -> list[dict]:
    """Return recent ingest task summaries for the runtime dashboard."""
    from ...celery_app import celery_app

    rows = []
    for task_id, submitted_at in list(_recent_task_ids)[:limit]:
        ar = celery_app.AsyncResult(task_id)
        info = ar.info if isinstance(ar.info, dict) else {}
        rows.append({
            "task_id":    task_id,
            "status":     _STATUS_MAP.get(ar.state, "unknown"),
            "step":       info.get("step", ""),
            "doc_id":     info.get("doc_id"),
            "sections":   info.get("sections", 0),
            "error":      str(ar.info) if ar.failed() else None,
            "created_at": submitted_at,
        })
    return rows


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
