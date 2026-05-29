"""
图谱链路预测 API

GET  /api/graph/predictions        — 读取 Redis 缓存的预测结果（需登录）
POST /api/admin/graph/predict      — 触发预测任务（管理员）
"""
import logging
import os

import redis
from fastapi import APIRouter, Depends, HTTPException

from ...auth.deps import get_admin_user, get_current_user
from ...db.models import User
from ...services.graph.link_prediction import get_cached_predictions
from ...tasks.graph_tasks import _PREDICTION_RUNNING_KEY, run_graph_prediction

logger = logging.getLogger(__name__)

router = APIRouter(tags=["graph"])


@router.get("/api/graph/predictions")
async def graph_predictions(_: User = Depends(get_current_user)):
    """返回缓存的链路预测结果。若缓存为空返回空列表。"""
    return get_cached_predictions()


@router.post("/api/admin/graph/predict")
async def trigger_link_prediction(
    top_k: int = 50,
    _: User = Depends(get_admin_user),
):
    """后台触发链路预测；结果写入 Redis，可通过 GET /api/graph/predictions 读取。"""
    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    if r.get(_PREDICTION_RUNNING_KEY):
        raise HTTPException(status_code=409, detail="预测任务正在运行中")

    run_graph_prediction.delay(top_k=top_k)
    return {"message": f"链路预测已启动（top_k={top_k}）", "running": True}
