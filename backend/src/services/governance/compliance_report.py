"""F7 — Compliance report generator and anomaly detector."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...services.audit.audit_models import AuditEvent

logger = logging.getLogger(__name__)

_ANOMALY_THRESHOLDS = {
    "failed_login_per_user":  5,    # > 5 failed logins in 1h → suspicious
    "bulk_delete_per_hour":   3,    # > 3 bulk deletes in 1h
    "export_per_hour":        10,   # > 10 exports in 1h
}


async def generate_report(db: AsyncSession, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await db.execute(
        select(AuditEvent)
        .where(AuditEvent.timestamp >= since)
        .order_by(AuditEvent.timestamp)
    )).scalars().all()

    actions = Counter(e.action for e in rows)
    event_types = Counter(e.event_type for e in rows)
    users = Counter(e.user_name for e in rows if e.user_name)
    failures = [e for e in rows if not e.success]

    # Daily activity breakdown
    daily: dict[str, int] = {}
    for e in rows:
        day = e.timestamp.date().isoformat()
        daily[day] = daily.get(day, 0) + 1

    return {
        "report_at": datetime.now(timezone.utc).isoformat(),
        "period_days": days,
        "total_events": len(rows),
        "total_failures": len(failures),
        "failure_rate": round(len(failures) / max(len(rows), 1) * 100, 2),
        "top_actions": dict(actions.most_common(10)),
        "top_event_types": dict(event_types.most_common(10)),
        "top_users": dict(users.most_common(10)),
        "daily_activity": daily,
        "anomalies": await detect_anomalies(db),
    }


async def detect_anomalies(db: AsyncSession) -> list[dict]:
    anomalies: list[dict] = []
    since_1h = datetime.now(timezone.utc) - timedelta(hours=1)
    try:
        # Failed logins per user in the last hour
        result = await db.execute(text("""
            SELECT user_name, COUNT(*) c FROM audit_events
            WHERE event_type = 'auth.failed_login' AND timestamp >= :since
            GROUP BY user_name HAVING COUNT(*) > :threshold
        """), {"since": since_1h,
               "threshold": _ANOMALY_THRESHOLDS["failed_login_per_user"]})
        for row in result.fetchall():
            anomalies.append({
                "type": "brute_force",
                "severity": "high",
                "message": f"用户 {row[0]} 1小时内登录失败 {row[1]} 次",
            })

        # Bulk deletes in the last hour
        result = await db.execute(text("""
            SELECT COUNT(*) FROM audit_events
            WHERE action = 'delete' AND timestamp >= :since
        """), {"since": since_1h})
        delete_count = result.scalar() or 0
        if delete_count > _ANOMALY_THRESHOLDS["bulk_delete_per_hour"]:
            anomalies.append({
                "type": "bulk_delete",
                "severity": "medium",
                "message": f"1小时内检测到 {delete_count} 次删除操作",
            })

        # High export volume
        result = await db.execute(text("""
            SELECT COUNT(*) FROM audit_events
            WHERE action = 'export' AND timestamp >= :since
        """), {"since": since_1h})
        export_count = result.scalar() or 0
        if export_count > _ANOMALY_THRESHOLDS["export_per_hour"]:
            anomalies.append({
                "type": "high_export",
                "severity": "low",
                "message": f"1小时内检测到 {export_count} 次数据导出",
            })
    except Exception as e:
        logger.warning("Anomaly detection error: %s", e)

    return anomalies
