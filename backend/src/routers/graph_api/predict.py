"""
图谱链路预测 API

GET  /api/graph/predictions        — 读取 Redis 缓存的预测结果（需登录）
POST /api/admin/graph/predict      — 触发预测任务（管理员）
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from ...auth.deps import get_admin_user, get_current_user
from ...core.database import get_driver
from ...db.models import User
from ...services.graph.link_prediction import get_cached_predictions, run_and_cache_predictions

logger = logging.getLogger(__name__)

router = APIRouter(tags=["graph"])

_running = False


@router.get("/api/graph/predictions")
async def graph_predictions(_: User = Depends(get_current_user)):
    """返回缓存的链路预测结果。若缓存为空返回空列表。"""
    return get_cached_predictions()


@router.post("/api/admin/graph/predict")
async def trigger_link_prediction(
    top_k: int = 50,
    _: User = Depends(get_admin_user),
    driver=Depends(get_driver),
):
    """后台触发链路预测；结果写入 Redis，可通过 GET /api/graph/predictions 读取。"""
    global _running
    if _running:
        raise HTTPException(status_code=409, detail="预测任务正在运行中")

    async def _run():
        global _running
        _running = True
        try:
            await asyncio.to_thread(run_and_cache_predictions, driver, top_k)
            logger.info("链路预测任务完成")
        except Exception as e:
            logger.exception("链路预测任务失败: %s", e)
        finally:
            _running = False

    asyncio.create_task(_run())
    return {"message": f"链路预测已启动（top_k={top_k}）", "running": True}
