import logging
from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from ...core.database import get_driver
from ...auth.deps import get_admin_user, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

@router.post("/documents/backfill/start", summary="启动图片补全任务")
async def backfill_start(_admin=Depends(get_admin_user)):
    """
    扫描所有没有 :Image 节点的 Document，逐份从 PDF 提取图片并写入图谱。
    任务已在运行时返回 409。
    """
    from ...services.ingestion.backfill_service import start_backfill, get_backfill_status
    status = get_backfill_status()
    if status["status"] == "running":
        raise HTTPException(409, "补全任务已在运行中")
    result = await start_backfill()
    return result


@router.post("/documents/backfill/pause", summary="暂停图片补全任务")
async def backfill_pause(_admin=Depends(get_admin_user)):
    """设置暂停标志，当前文档处理完后进入等待状态。"""
    from ...services.ingestion.backfill_service import pause_backfill, get_backfill_status
    result = pause_backfill()
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    return {**result, "progress": get_backfill_status()}


@router.post("/documents/backfill/resume", summary="恢复图片补全任务")
async def backfill_resume(_admin=Depends(get_admin_user)):
    """删除暂停标志，继续处理剩余文档。"""
    from ...services.ingestion.backfill_service import resume_backfill, get_backfill_status
    result = resume_backfill()
    return {**result, "progress": get_backfill_status()}


@router.get("/documents/backfill/status", summary="查询图片补全进度")
async def backfill_status(_user=Depends(get_current_user)):
    """
    返回补全任务当前状态（所有已登录用户可查询）：
    - status: idle / running / paused / completed
    - total / done / percent
    - current_doc：正在处理的文档
    - elapsed_seconds / estimated_remaining_seconds
    """
    from ...services.ingestion.backfill_service import get_backfill_status
    return get_backfill_status()


@router.post("/documents/backfill/stop", summary="停止图片补全任务")
async def backfill_stop(_admin=Depends(get_admin_user)):
    """停止任务并清除所有进度数据，状态归 idle。"""
    from ...services.ingestion.backfill_service import stop_backfill
    result = stop_backfill()
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    return result
