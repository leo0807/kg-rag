"""
Multi-channel alert management.

POST /api/admin/alerts/test    — 发送测试告警
POST /api/admin/alerts/silence — 添加静默规则（维护窗口）
GET  /api/admin/alerts/silences — 查询当前有效静默规则
DELETE /api/admin/alerts/silence/{id} — 手动取消静默
GET  /api/admin/alerts/history — 告警历史（来自 audit_logs）
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import AuditLog, SystemSetting, User
from ...db.session import get_db
from ...services.monitoring.alert_sender import AlertSender

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/alerts", tags=["admin-alerts"])

_sender = AlertSender()

# ---------------------------------------------------------------------------
# In-memory silence store (persisted to SystemSetting as JSON)
# ---------------------------------------------------------------------------

_SILENCE_KEY = "alert_silences"


async def _load_silences(db: AsyncSession) -> list[dict]:
    import json  # noqa: PLC0415
    row = await db.scalar(select(SystemSetting.value).where(SystemSetting.key == _SILENCE_KEY))
    if not row:
        return []
    try:
        return json.loads(row)
    except Exception:
        return []


async def _save_silences(db: AsyncSession, silences: list[dict]) -> None:
    import json  # noqa: PLC0415
    existing = await db.scalar(select(SystemSetting).where(SystemSetting.key == _SILENCE_KEY))
    payload  = json.dumps(silences)
    if existing:
        existing.value = payload
    else:
        db.add(SystemSetting(key=_SILENCE_KEY, value=payload))
    await db.commit()


def _active_silences(silences: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [s for s in silences if s.get("expires_at", "") > now]


async def _is_silenced(db: AsyncSession, rule: str) -> bool:
    silences = _active_silences(await _load_silences(db))
    return any(s.get("rule") == rule or s.get("rule") == "*" for s in silences)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class TestAlertBody(BaseModel):
    message: str = "测试告警消息"
    level:   str = "warning"  # info | warning | error | critical
    channel: str | None = None  # dingtalk | wecom | email | None (all)


@router.post("/test")
async def send_test_alert(
    body: TestAlertBody,
    admin: User = Depends(get_admin_user),
    db:    AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Send a test alert to verify channel configuration."""
    msg = f"[TEST] {body.message} (by {admin.username})"
    await _sender.send(msg, level=body.level, channel=body.channel)  # type: ignore[arg-type]
    # Persist to audit_logs
    db.add(AuditLog(
        user_id=str(admin.id),
        action="alert.test",
        resource_type="alert",
        detail={"message": body.message, "level": body.level},
    ))
    await db.commit()
    return {"ok": True, "message": msg, "level": body.level}


class SilenceBody(BaseModel):
    rule:        str             # alert rule name or "*" for all
    reason:      str = ""
    duration_minutes: int = 60


@router.post("/silence")
async def add_silence(
    body:  SilenceBody,
    admin: User = Depends(get_admin_user),
    db:    AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Silence a named alert rule for a maintenance window."""
    silences  = await _load_silences(db)
    # Remove expired first
    silences  = _active_silences(silences)
    expires   = (datetime.now(timezone.utc) + timedelta(minutes=body.duration_minutes)).isoformat()
    sid       = str(uuid.uuid4())[:8]
    silences.append({
        "id":         sid,
        "rule":       body.rule,
        "reason":     body.reason,
        "created_by": str(admin.id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires,
    })
    await _save_silences(db, silences)
    db.add(AuditLog(
        user_id=str(admin.id),
        action="alert.silence",
        resource_type="alert",
        detail={"rule": body.rule, "expires_at": expires},
    ))
    await db.commit()
    return {"ok": True, "silence_id": sid, "expires_at": expires}


@router.get("/silences")
async def list_silences(
    _:  User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    silences = _active_silences(await _load_silences(db))
    return {"count": len(silences), "silences": silences}


@router.delete("/silence/{silence_id}")
async def remove_silence(
    silence_id: str,
    _:  User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    silences = await _load_silences(db)
    updated  = [s for s in silences if s["id"] != silence_id]
    if len(updated) == len(silences):
        raise HTTPException(status_code=404, detail="Silence not found")
    await _save_silences(db, updated)
    return {"ok": True, "removed": silence_id}


@router.get("/history")
async def alert_history(
    days: int = Query(default=7, ge=1, le=90),
    _:  User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return alert history from audit_logs."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await db.execute(
        select(AuditLog).where(
            AuditLog.action.like("alert.%"),
            AuditLog.created_at >= since,
        ).order_by(AuditLog.created_at.desc()).limit(200)
    )
    events = [
        {
            "id":         str(row.id),
            "action":     row.action,
            "detail":     row.detail,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows.scalars()
    ]
    return {"days": days, "count": len(events), "events": events}
