"""
GET  /api/admin/processing/status  — 当前处理任务实时状态
POST /api/admin/processing/retry/{task_id} — 重试失败任务
POST /api/admin/processing/clear-completed — 清除今日统计
"""
from fastapi import APIRouter, Depends, HTTPException

from ...auth.deps import get_admin_user
from ...services.ingestion.batch_ingest_service import (
    clear_completed_tasks,
    get_processing_status,
    retry_task,
)

router = APIRouter(prefix="/api/admin/processing", tags=["admin_processing"])


@router.get("/status")
async def processing_status(_admin=Depends(get_admin_user)):
    return get_processing_status()


@router.post("/retry/{task_id}")
async def retry_processing_task(task_id: str, _admin=Depends(get_admin_user)):
    result = await retry_task(task_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@router.post("/clear-completed")
async def clear_completed(_admin=Depends(get_admin_user)):
    return clear_completed_tasks()
