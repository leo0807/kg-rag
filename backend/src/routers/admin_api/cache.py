"""
src/routers/admin_cache.py
管理员专用 API：语义缓存配置、统计、手动失效
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from .entities import _require_admin
from ...db.models import User
from ...db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


class CacheConfigUpdate(BaseModel):
    threshold: float | None = None
    ttl:       int   | None = None
    enabled:   bool  | None = None


@router.get("/semantic-cache/config")
async def get_cache_config(_: User = Depends(_require_admin)):
    """读取当前语义缓存配置"""
    from ...services.semantic_cache import get_config
    return get_config()


@router.put("/semantic-cache/config")
async def update_cache_config(
    body: CacheConfigUpdate,
    _: User = Depends(_require_admin),
):
    """更新语义缓存配置（threshold / ttl / enabled）"""
    from ...services.semantic_cache import set_config
    set_config(threshold=body.threshold, ttl=body.ttl, enabled=body.enabled)
    from ...services.semantic_cache import get_config
    return {"ok": True, "config": get_config()}


@router.get("/semantic-cache/stats")
async def get_cache_stats(
    days: int = 30,
    _: User = Depends(_require_admin),
):
    """活跃缓存条目数 + 命中统计（节省 token 和费用）"""
    from ...services.semantic_cache import get_stats
    from ...db.models import CacheHit

    store_stats = get_stats()
    since = datetime.utcnow() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                func.count(CacheHit.id).label("hit_count"),
                func.sum(CacheHit.prompt_tokens_saved).label("tokens_saved"),
                func.sum(CacheHit.cost_saved_usd).label("cost_saved_usd"),
                func.avg(CacheHit.similarity).label("avg_similarity"),
            ).where(CacheHit.created_at >= since)
        )
        row = result.one()

        # 按策略拆分命中分布
        by_strategy_result = await db.execute(
            select(
                CacheHit.strategy,
                func.count(CacheHit.id).label("hit_count"),
                func.avg(CacheHit.similarity).label("avg_similarity"),
            )
            .where(CacheHit.created_at >= since)
            .group_by(CacheHit.strategy)
        )
        by_strategy = [
            {
                "strategy":       r.strategy or "parallel",
                "hit_count":      int(r.hit_count),
                "avg_similarity": round(float(r.avg_similarity or 0), 4),
            }
            for r in by_strategy_result.all()
        ]

    CNY_RATE = 7.25
    cost_usd = float(row.cost_saved_usd or 0)
    return {
        "days":  days,
        "since": since.isoformat(),
        "store": store_stats,
        "hits": {
            "hit_count":      int(row.hit_count or 0),
            "tokens_saved":   int(row.tokens_saved or 0),
            "cost_saved_usd": round(cost_usd, 6),
            "cost_saved_cny": round(cost_usd * CNY_RATE, 4),
            "avg_similarity": round(float(row.avg_similarity or 0), 4),
        },
        "by_strategy": by_strategy,
    }


@router.post("/cache/invalidate/{doc_id}")
async def invalidate_cache(
    doc_id: str,
    _: User = Depends(_require_admin),
):
    """按 doc_id 批量失效相关语义缓存条目"""
    from ...services.semantic_cache import invalidate_by_doc
    import asyncio
    count = await asyncio.to_thread(invalidate_by_doc, doc_id)
    return {"ok": True, "doc_id": doc_id, "invalidated": count}
