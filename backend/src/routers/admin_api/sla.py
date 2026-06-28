"""
SLA availability statistics.

GET /api/admin/sla  — 30 天 SLA 滚动统计 + 每日可用性热力日历
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import User
from ...db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/sla", tags=["admin-sla"])

# Endpoint scopes to track for SLA
_SLA_ENDPOINTS = ("/api/query", "/api/query/stream")

# Target SLA (99.9 % = < 43.8 min downtime/month)
SLA_TARGET = float(0.999)


async def _ensure_table(db: AsyncSession) -> None:
    """Create sla_minute_log table if it doesn't exist."""
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS sla_minute_log (
            id          SERIAL PRIMARY KEY,
            minute_ts   TIMESTAMPTZ NOT NULL,
            endpoint    TEXT NOT NULL,
            total_req   INT  DEFAULT 0,
            success_req INT  DEFAULT 0,
            UNIQUE (minute_ts, endpoint)
        )
    """))
    await db.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_sla_minute_ts ON sla_minute_log (minute_ts)
    """))
    await db.commit()


async def _daily_availability(db: AsyncSession, d: date, endpoint: str) -> float | None:
    """Return availability ratio for a given day and endpoint (None if no data)."""
    day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    day_end   = day_start + timedelta(days=1)
    row = await db.execute(text("""
        SELECT SUM(total_req) AS t, SUM(success_req) AS s
        FROM sla_minute_log
        WHERE minute_ts >= :start AND minute_ts < :end AND endpoint = :ep
    """), {"start": day_start, "end": day_end, "ep": endpoint})
    r = row.fetchone()
    if not r or not r[0]:
        return None
    return float(r[1]) / float(r[0])


@router.get("")
async def sla_report(
    days: int = Query(default=30, ge=7, le=90),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return rolling SLA for the past N days.

    Response includes:
    - overall_sla         — weighted availability across tracked endpoints
    - target_met          — whether SLA target (99.9%) is met
    - downtime_minutes    — total outage minutes this period
    - calendar            — per-day availability heatmap (0.0–1.0 or null)
    - endpoint_breakdown  — per-endpoint SLA
    """
    await _ensure_table(db)

    today = datetime.now(timezone.utc).date()
    days_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]

    endpoint_breakdown: dict[str, dict] = {}
    calendar_by_ep: dict[str, list] = {}

    for ep in _SLA_ENDPOINTS:
        daily: list[float | None] = []
        for d in days_list:
            avail = await _daily_availability(db, d, ep)
            daily.append(avail)

        valid = [v for v in daily if v is not None]
        ep_sla = sum(valid) / len(valid) if valid else None
        data_days = len(valid)

        # Downtime = minutes in day with availability < 99.9%
        downtime_min = sum(
            (1 - v) * 1440 for v in valid if v is not None and v < SLA_TARGET
        )

        endpoint_breakdown[ep] = {
            "sla":            round(ep_sla, 5) if ep_sla is not None else None,
            "target_met":     (ep_sla is not None and ep_sla >= SLA_TARGET),
            "downtime_minutes": round(downtime_min, 1),
            "data_days":      data_days,
        }
        calendar_by_ep[ep] = [
            {"date": str(days_list[i]), "availability": daily[i]}
            for i in range(len(days_list))
        ]

    # Aggregate across endpoints
    valid_slas = [v["sla"] for v in endpoint_breakdown.values() if v["sla"] is not None]
    overall_sla = sum(valid_slas) / len(valid_slas) if valid_slas else None
    total_downtime = sum(v["downtime_minutes"] for v in endpoint_breakdown.values())

    return {
        "period_days":      days,
        "sla_target":       SLA_TARGET,
        "overall_sla":      round(overall_sla, 5) if overall_sla is not None else None,
        "target_met":       (overall_sla is not None and overall_sla >= SLA_TARGET),
        "downtime_minutes": round(total_downtime, 1),
        "endpoint_breakdown": endpoint_breakdown,
        "calendar":         calendar_by_ep,
    }


@router.post("/record")
async def record_minute(
    endpoint: str,
    total:   int,
    success: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Record a one-minute availability sample.
    Called by the APScheduler heartbeat (internal use).
    """
    await _ensure_table(db)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    await db.execute(text("""
        INSERT INTO sla_minute_log (minute_ts, endpoint, total_req, success_req)
        VALUES (:ts, :ep, :total, :success)
        ON CONFLICT (minute_ts, endpoint) DO UPDATE
          SET total_req = sla_minute_log.total_req + :total,
              success_req = sla_minute_log.success_req + :success
    """), {"ts": now, "ep": endpoint, "total": total, "success": success})
    await db.commit()
    return {"ok": True}
