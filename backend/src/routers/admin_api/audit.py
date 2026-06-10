"""Admin API — F1.4 Audit log queries."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import User
from ...db.session import get_db
from ...services.audit.audit_models import AuditEvent

router = APIRouter(prefix="/api/admin/audit", tags=["admin-audit"])


def _fmt(e: AuditEvent) -> dict:
    return {
        "id": e.id, "event_type": e.event_type, "action": e.action,
        "user_id": e.user_id, "user_name": e.user_name, "user_role": e.user_role,
        "ip_address": e.ip_address,
        "resource_type": e.resource_type, "resource_id": e.resource_id,
        "resource_name": e.resource_name,
        "success": e.success, "error_message": e.error_message,
        "trace_id": e.trace_id, "request_path": e.request_path,
        "request_method": e.request_method,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
    }


@router.get("/events")
async def list_events(
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
    search: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditEvent).order_by(desc(AuditEvent.timestamp))
    conditions = []
    if user_id:
        conditions.append(AuditEvent.user_id == user_id)
    if event_type:
        conditions.append(AuditEvent.event_type.ilike(f"%{event_type}%"))
    if resource_type:
        conditions.append(AuditEvent.resource_type == resource_type)
    if action:
        conditions.append(AuditEvent.action == action)
    if success is not None:
        conditions.append(AuditEvent.success == success)
    if search:
        conditions.append(or_(
            AuditEvent.resource_name.ilike(f"%{search}%"),
            AuditEvent.request_path.ilike(f"%{search}%"),
            AuditEvent.user_name.ilike(f"%{search}%"),
        ))
    if since:
        try:
            conditions.append(AuditEvent.timestamp >= datetime.fromisoformat(since))
        except ValueError:
            pass
    if until:
        try:
            conditions.append(AuditEvent.timestamp <= datetime.fromisoformat(until))
        except ValueError:
            pass
    if conditions:
        q = q.where(and_(*conditions))

    all_rows = (await db.execute(q)).scalars().all()
    offset = (page - 1) * page_size
    return {
        "total": len(all_rows),
        "page": page,
        "page_size": page_size,
        "events": [_fmt(e) for e in all_rows[offset: offset + page_size]],
    }


@router.get("/events/{event_id}")
async def get_event(
    event_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    e = await db.get(AuditEvent, event_id)
    if not e:
        from fastapi import HTTPException
        raise HTTPException(404, "事件不存在")
    return {
        **_fmt(e),
        "before_state": e.before_state,
        "after_state": e.after_state,
        "changes": e.changes,
        "user_agent": e.user_agent,
        "session_id": e.session_id,
    }


@router.get("/users/{user_id}/activity")
async def user_activity(
    user_id: str, limit: int = 100,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(AuditEvent)
        .where(AuditEvent.user_id == user_id)
        .order_by(desc(AuditEvent.timestamp))
        .limit(limit)
    )).scalars().all()
    from collections import Counter
    actions = Counter(e.action for e in rows)
    resources = Counter(e.resource_type for e in rows if e.resource_type)
    return {
        "user_id": user_id,
        "total_actions": len(rows),
        "action_breakdown": dict(actions),
        "resource_breakdown": dict(resources),
        "recent": [_fmt(e) for e in rows[:20]],
    }


@router.get("/resources/{resource_type}/{resource_id}/history")
async def resource_history(
    resource_type: str, resource_id: str, limit: int = 50,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(AuditEvent)
        .where(AuditEvent.resource_type == resource_type,
               AuditEvent.resource_id == resource_id)
        .order_by(desc(AuditEvent.timestamp))
        .limit(limit)
    )).scalars().all()
    return {"resource_type": resource_type, "resource_id": resource_id,
            "history": [_fmt(e) for e in rows]}


@router.post("/export")
async def export_audit(
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditEvent).order_by(desc(AuditEvent.timestamp)).limit(10000)
    conditions = []
    if user_id:
        conditions.append(AuditEvent.user_id == user_id)
    if event_type:
        conditions.append(AuditEvent.event_type.ilike(f"%{event_type}%"))
    if since:
        try:
            conditions.append(AuditEvent.timestamp >= datetime.fromisoformat(since))
        except ValueError:
            pass
    if conditions:
        q = q.where(and_(*conditions))
    rows = (await db.execute(q)).scalars().all()
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=[
        "timestamp", "event_type", "action", "user_id", "user_name",
        "ip_address", "resource_type", "resource_id", "success", "request_path",
    ])
    w.writeheader()
    for e in rows:
        w.writerow({
            "timestamp": e.timestamp.isoformat() if e.timestamp else "",
            "event_type": e.event_type, "action": e.action,
            "user_id": e.user_id or "", "user_name": e.user_name or "",
            "ip_address": e.ip_address or "",
            "resource_type": e.resource_type or "", "resource_id": e.resource_id or "",
            "success": e.success, "request_path": e.request_path or "",
        })
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=audit_log.csv"})
