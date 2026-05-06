"""
GET /api/admin/health — 系统综合健康快照（供前端健康看板 30 秒轮询）

聚合：图谱统计、LLM 用量、服务健康、冲突待办、处理任务状态、近期事件
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from neo4j import Driver
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import AuditLog, ConflictRecord, LLMUsage, User
from ...db.session import get_db
from ...services.infra.health import health_monitor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/health", tags=["admin"])


async def _graph_stats(driver: Driver) -> dict:
    try:
        with driver.session() as session:
            row = session.run(
                "MATCH (n) RETURN count(n) AS nodes, "
                "[(n) WHERE NOT (n)--() | n][0..1] AS orphan_sample "
                "UNION ALL MATCH ()-[r]->() RETURN count(r) AS nodes, [] AS orphan_sample"
            ).data()
            node_count = int(row[0]["nodes"]) if row else 0
            rel_count = int(row[1]["nodes"]) if len(row) > 1 else 0
            orphan_row = session.run(
                "MATCH (n) WHERE NOT (n)--() RETURN count(n) AS c"
            ).single()
            orphan_count = int(orphan_row["c"]) if orphan_row else 0
        health_score = max(
            0.0,
            1.0 - (orphan_count / max(node_count, 1)) * 0.5
            - (0.2 if rel_count == 0 else 0),
        )
        return {
            "node_count": node_count,
            "rel_count": rel_count,
            "orphan_count": orphan_count,
            "health_score": round(health_score, 3),
        }
    except Exception as e:
        logger.warning("图谱统计失败: %s", e)
        return {"node_count": 0, "rel_count": 0, "orphan_count": 0, "health_score": 0.0}


async def _llm_stats(db: AsyncSession) -> dict:
    since_7d = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    row = (await db.execute(
        select(
            func.count(LLMUsage.id).label("requests"),
            func.coalesce(func.avg(LLMUsage.latency_ms), 0).label("avg_latency_ms"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0).label("cost_usd"),
        ).where(LLMUsage.created_at >= since_7d)
    )).one()
    return {
        "queries_7d": int(row.requests or 0),
        "avg_latency_ms": round(float(row.avg_latency_ms or 0)),
        "cost_usd_7d": round(float(row.cost_usd or 0), 4),
    }


async def _daily_trend(db: AsyncSession, days: int = 7) -> list[dict]:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    rows = (await db.execute(
        select(
            func.date(LLMUsage.created_at).label("date"),
            func.count(LLMUsage.id).label("requests"),
            func.coalesce(func.avg(LLMUsage.latency_ms), 0).label("avg_latency_ms"),
        )
        .where(LLMUsage.created_at >= since)
        .group_by(func.date(LLMUsage.created_at))
        .order_by(func.date(LLMUsage.created_at))
    )).all()
    return [
        {"date": str(r.date), "requests": int(r.requests or 0),
         "avg_latency_ms": round(float(r.avg_latency_ms or 0))}
        for r in rows
    ]


async def _conflict_pending(db: AsyncSession) -> int:
    return int((await db.execute(
        select(func.count(ConflictRecord.id)).where(ConflictRecord.status == "pending")
    )).scalar() or 0)


async def _recent_events(db: AsyncSession, limit: int = 8) -> list[dict]:
    rows = (await db.execute(
        select(AuditLog, User.username)
        .join(User, AuditLog.user_id == User.id, isouter=True)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )).all()
    return [
        {"action": log.action, "resource": log.resource,
         "username": username or "—", "created_at": log.created_at.isoformat()}
        for log, username in rows
    ]


@router.get("")
async def health_snapshot(
    _: User = Depends(get_admin_user),
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
):
    import asyncio
    graph, llm, trend, conflicts, events = await asyncio.gather(
        _graph_stats(driver),
        _llm_stats(db),
        _daily_trend(db),
        _conflict_pending(db),
        _recent_events(db),
    )

    services = health_monitor.to_dict()
    # 内存信息
    try:
        from ...services.model_manager import model_manager
        memory = model_manager.memory_info()
    except Exception:
        memory = {"total_gb": 0, "used_gb": 0, "available_gb": 0, "percent": 0, "models_loaded": []}
    # compute system health score
    svc_ok = sum(1 for s in services.values() if s.get("is_ok", False))
    svc_total = len(services) or 1
    health_score = round(graph["health_score"] * 0.5 + (svc_ok / svc_total) * 0.5, 3)

    # pending actions
    actions = []
    if conflicts > 0:
        actions.append({"type": "conflict", "label": f"{conflicts} 条冲突待审核", "href": "/admin/conflicts"})
    if llm["avg_latency_ms"] > 5000:
        actions.append({"type": "warning", "label": f"平均响应 {llm['avg_latency_ms']}ms，超过阈值", "href": "/admin/usage"})
    if graph["health_score"] < 0.8:
        actions.append({"type": "warning", "label": "图谱孤立节点占比偏高", "href": "/admin/cypher"})

    return {
        "health_score": health_score,
        "graph": graph,
        "llm": llm,
        "trend": trend,
        "services": services,
        "conflict_pending": conflicts,
        "actions": actions,
        "recent_events": events,
        "memory": memory,
    }
