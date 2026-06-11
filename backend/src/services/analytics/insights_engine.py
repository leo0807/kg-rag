"""
J2.1: Business insights engine — aggregates usage, quality, knowledge, and ops metrics.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _days_ago(n: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=n)


PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}


async def _safe(coro, default=None):
    try:
        return await coro
    except Exception as e:
        logger.debug("insight query failed: %s", e)
        return default


class InsightsEngine:
    """Generates aggregated business insights from multiple data stores."""

    # ── Usage ────────────────────────────────────────────────────────────────

    async def usage_insights(
        self, db: AsyncSession, period: str = "30d", tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        days = PERIOD_DAYS.get(period, 30)
        start = _days_ago(days)

        results = await asyncio.gather(
            _safe(self._count_active_users(db, start, tenant_id), 0),
            _safe(self._query_trend(db, start, tenant_id), []),
            _safe(self._top_questions(db, start, tenant_id), []),
            _safe(self._engagement_metrics(db, start, tenant_id), {}),
        )
        active, trend, top_q, engagement = results

        prev_active = await _safe(
            self._count_active_users(db, _days_ago(days * 2), _days_ago(days)), 1
        )
        growth = round((active - prev_active) / max(prev_active, 1) * 100, 1)

        return {
            "active_users": active,
            "daily_query_trend": trend,
            "top_topics": top_q,
            "user_engagement": engagement,
            "growth_rate": growth,
        }

    async def _count_active_users(
        self, db: AsyncSession, start: datetime, tenant_id: Optional[str]
    ) -> int:
        q = "SELECT COUNT(DISTINCT user_id) FROM audit_logs WHERE timestamp >= :start"
        params: Dict[str, Any] = {"start": start}
        if tenant_id:
            q += " AND tenant_id = :tid"
            params["tid"] = tenant_id
        r = await db.execute(text(q), params)
        return r.scalar() or 0

    async def _query_trend(
        self, db: AsyncSession, start: datetime, tenant_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        q = """
            SELECT DATE(timestamp) AS date,
                   COUNT(*) AS queries,
                   SUM(CASE WHEN event_type='error' THEN 1 ELSE 0 END) AS errors
            FROM audit_logs WHERE timestamp >= :start
            GROUP BY DATE(timestamp) ORDER BY date
        """
        r = await db.execute(text(q), {"start": start})
        return [{"date": str(row.date), "queries": row.queries, "errors": row.errors}
                for row in r.fetchall()]

    async def _top_questions(
        self, db: AsyncSession, start: datetime, tenant_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        q = """
            SELECT resource_type AS topic, COUNT(*) AS count
            FROM audit_logs WHERE timestamp >= :start AND resource_type IS NOT NULL
            GROUP BY resource_type ORDER BY count DESC LIMIT 10
        """
        r = await db.execute(text(q), {"start": start})
        return [{"topic": row.topic, "count": row.count} for row in r.fetchall()]

    async def _engagement_metrics(
        self, db: AsyncSession, start: datetime, tenant_id: Optional[str]
    ) -> Dict[str, Any]:
        q = "SELECT COUNT(*) as total, COUNT(DISTINCT user_id) AS users FROM audit_logs WHERE timestamp >= :start"
        r = await db.execute(text(q), {"start": start})
        row = r.fetchone()
        total = row.total if row else 0
        users = row.users if row else 1
        return {"avg_queries_per_user": round(total / max(users, 1), 1), "total_queries": total}

    # ── Quality ──────────────────────────────────────────────────────────────

    async def quality_insights(self, db: AsyncSession, period: str = "30d") -> Dict[str, Any]:
        days = PERIOD_DAYS.get(period, 30)
        start = _days_ago(days)
        results = await asyncio.gather(
            _safe(self._accuracy_over_time(db, start), []),
            _safe(self._feedback_dist(db, start), []),
            _safe(self._top_problems(db, start), []),
        )
        return {
            "accuracy_trend": results[0],
            "feedback_distribution": results[1],
            "problematic_areas": results[2],
        }

    async def _accuracy_over_time(self, db: AsyncSession, start: datetime) -> List[Dict[str, Any]]:
        q = """
            SELECT DATE(created_at) AS date, AVG(rating) AS avg_score, COUNT(*) AS count
            FROM qa_feedback WHERE created_at >= :start
            GROUP BY DATE(created_at) ORDER BY date
        """
        r = await db.execute(text(q), {"start": start})
        return [{"date": str(row.date), "avg_score": round(float(row.avg_score or 0), 2),
                 "count": row.count} for row in r.fetchall()]

    async def _feedback_dist(self, db: AsyncSession, start: datetime) -> List[Dict[str, Any]]:
        q = "SELECT rating, COUNT(*) AS count FROM qa_feedback WHERE created_at >= :start GROUP BY rating ORDER BY rating"
        r = await db.execute(text(q), {"start": start})
        return [{"rating": row.rating, "count": row.count} for row in r.fetchall()]

    async def _top_problems(self, db: AsyncSession, start: datetime) -> List[Dict[str, Any]]:
        q = """
            SELECT resource_type AS area, COUNT(*) AS count
            FROM audit_logs WHERE event_type = 'error' AND timestamp >= :start AND resource_type IS NOT NULL
            GROUP BY area ORDER BY count DESC LIMIT 10
        """
        r = await db.execute(text(q), {"start": start})
        return [{"area": row.area, "count": row.count} for row in r.fetchall()]

    # ── Knowledge ────────────────────────────────────────────────────────────

    async def knowledge_insights(self, db: AsyncSession, period: str = "30d") -> Dict[str, Any]:
        days = PERIOD_DAYS.get(period, 30)
        start = _days_ago(days)
        results = await asyncio.gather(
            _safe(self._most_queried_docs(db, start), []),
            _safe(self._topic_distribution(db), []),
        )
        return {"hot_documents": results[0], "topic_distribution": results[1]}

    async def _most_queried_docs(self, db: AsyncSession, start: datetime) -> List[Dict[str, Any]]:
        q = """
            SELECT resource_id AS doc_id, COUNT(*) AS queries
            FROM audit_logs WHERE timestamp >= :start AND resource_id IS NOT NULL
            GROUP BY resource_id ORDER BY queries DESC LIMIT 10
        """
        r = await db.execute(text(q), {"start": start})
        return [{"doc_id": row.doc_id, "queries": row.queries} for row in r.fetchall()]

    async def _topic_distribution(self, db: AsyncSession) -> List[Dict[str, Any]]:
        q = "SELECT resource_type AS topic, COUNT(*) AS count FROM audit_logs WHERE resource_type IS NOT NULL GROUP BY resource_type ORDER BY count DESC LIMIT 20"
        r = await db.execute(text(q))
        return [{"topic": row.topic, "count": row.count} for row in r.fetchall()]

    # ── Operations ───────────────────────────────────────────────────────────

    async def operations_insights(self, db: AsyncSession, period: str = "30d") -> Dict[str, Any]:
        days = PERIOD_DAYS.get(period, 30)
        start = _days_ago(days)
        results = await asyncio.gather(
            _safe(self._qps_trend(db, start), []),
            _safe(self._error_analysis(db, start), []),
        )
        return {"qps_trend": results[0], "error_patterns": results[1]}

    async def _qps_trend(self, db: AsyncSession, start: datetime) -> List[Dict[str, Any]]:
        q = """
            SELECT DATE_TRUNC('hour', timestamp) AS hour, COUNT(*) AS requests
            FROM audit_logs WHERE timestamp >= :start
            GROUP BY hour ORDER BY hour LIMIT 168
        """
        r = await db.execute(text(q), {"start": start})
        return [{"hour": str(row.hour), "requests": row.requests} for row in r.fetchall()]

    async def _error_analysis(self, db: AsyncSession, start: datetime) -> List[Dict[str, Any]]:
        q = """
            SELECT action, COUNT(*) AS count
            FROM audit_logs WHERE event_type='error' AND timestamp >= :start
            GROUP BY action ORDER BY count DESC LIMIT 10
        """
        r = await db.execute(text(q), {"start": start})
        return [{"action": row.action, "count": row.count} for row in r.fetchall()]


insights_engine = InsightsEngine()
