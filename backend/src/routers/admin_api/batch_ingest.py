import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from ...auth.deps import get_admin_user
from ...services.ingestion.batch_ingest_service import (
    start_batch_ingest, pause_batch, resume_batch, stop_batch, get_batch_status
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/batch", tags=["admin_batch"])

@router.post("/start")
async def start_batch(
    directory: str = Body(..., embed=True),
    _admin = Depends(get_admin_user)
):
    """启动指定目录的批量入库任务"""
    result = await start_batch_ingest(directory)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result

@router.post("/pause")
async def pause_batch_task(_admin = Depends(get_admin_user)):
    """暂停当前任务"""
    return pause_batch()

@router.post("/resume")
async def resume_batch_task(_admin = Depends(get_admin_user)):
    """恢复当前任务"""
    return resume_batch()

@router.post("/stop")
async def stop_batch_task(_admin = Depends(get_admin_user)):
    """停止当前任务"""
    return stop_batch()

@router.get("/status")
async def batch_status(_admin = Depends(get_admin_user)):
    """获取批量任务状态和日志"""
    return get_batch_status()
