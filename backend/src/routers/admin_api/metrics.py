"""
GET /api/admin/metrics/performance  — 延迟 P50/P95 及吞吐量
GET /api/admin/metrics/errors       — 近期错误事件列表
GET /api/admin/metrics/volume       — 每小时查询量趋势
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import LLMUsage, SystemErrorEvent
from ...db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/metrics", tags=["admin"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _percentile_sql(col: str, p: float) -> str:
    return f"percentile_cont({p}) WITHIN GROUP (ORDER BY {col})"


@router.get("/performance")
async def get_performance_metrics(
    days: int = Query(default=7, ge=1, le=90),
    _user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """返回按策略分组的 P50/P95 延迟和成功率统计。"""
    since = _utc_now() - timedelta(days=days)

    rows = await db.execute(
        text("""
            SELECT
                strategy,
                COUNT(*)                                                       AS total,
                ROUND(AVG(latency_ms))::int                                    AS avg_ms,
                ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)) AS p50_ms,
                ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)) AS p95_ms,
                SUM(prompt_tokens + completion_tokens)                         AS total_tokens,
                ROUND(SUM(cost_usd)::numeric, 4)                               AS total_cost
            FROM llm_usage
            WHERE created_at >= :since
            GROUP BY strategy
            ORDER BY total DESC
        """),
        {"since": since},
    )
    strategies = [dict(r._mapping) for r in rows]

    overall = await db.execute(
        text("""
            SELECT
                COUNT(*)                                                        AS total,
                ROUND(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)) AS p50_ms,
                ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)) AS p95_ms,
                ROUND(AVG(latency_ms))::int                                     AS avg_ms,
                SUM(prompt_tokens + completion_tokens)                          AS total_tokens,
                ROUND(SUM(cost_usd)::numeric, 4)                                AS total_cost
            FROM llm_usage
            WHERE created_at >= :since
        """),
        {"since": since},
    )
    row = overall.first()
    summary = dict(row._mapping) if row else {}

    return {"days": days, "summary": summary, "by_strategy": strategies}


@router.get("/errors")
async def get_error_events(
    days: int = Query(default=3, ge=1, le=30),
    limit: int = Query(default=50, ge=1, le=200),
    _user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """返回近期 500 错误与 LLM 失败事件。"""
    since = _utc_now() - timedelta(days=days)

    result = await db.execute(
        select(SystemErrorEvent)
        .where(SystemErrorEvent.created_at >= since)
        .order_by(SystemErrorEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()

    counts = await db.execute(
        select(
            SystemErrorEvent.kind,
            SystemErrorEvent.error_type,
            func.count().label("cnt"),
        )
        .where(SystemErrorEvent.created_at >= since)
        .group_by(SystemErrorEvent.kind, SystemErrorEvent.error_type)
        .order_by(func.count().desc())
        .limit(20)
    )

    return {
        "days":   days,
        "total":  len(events),
        "events": [
            {
                "id":         e.id,
                "kind":       e.kind,
                "path":       e.path,
                "error_type": e.error_type,
                "message":    e.message[:200],
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "top_errors": [
            {"kind": r.kind, "error_type": r.error_type, "count": r.cnt}
            for r in counts
        ],
    }


@router.get("/volume")
async def get_query_volume(
    days: int = Query(default=7, ge=1, le=30),
    _user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """返回每小时查询量趋势（按策略拆分）。"""
    since = _utc_now() - timedelta(days=days)

    rows = await db.execute(
        text("""
            SELECT
                date_trunc('hour', created_at)  AS hour,
                strategy,
                COUNT(*)                         AS queries
            FROM llm_usage
            WHERE created_at >= :since
            GROUP BY hour, strategy
            ORDER BY hour
        """),
        {"since": since},
    )
    hourly = [
        {
            "hour":     r.hour.isoformat() if r.hour else None,
            "strategy": r.strategy,
            "queries":  r.queries,
        }
        for r in rows
    ]

    daily = await db.execute(
        text("""
            SELECT
                date_trunc('day', created_at) AS day,
                COUNT(*)                       AS queries,
                SUM(cost_usd)                  AS cost_usd
            FROM llm_usage
            WHERE created_at >= :since
            GROUP BY day
            ORDER BY day
        """),
        {"since": since},
    )
    daily_data = [
        {
            "day":      r.day.isoformat() if r.day else None,
            "queries":  r.queries,
            "cost_usd": float(r.cost_usd or 0),
        }
        for r in daily
    ]

    return {"days": days, "hourly": hourly, "daily": daily_data}
