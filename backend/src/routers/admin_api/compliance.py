"""F4.1/F4.3 — GDPR-style user data export + content moderation API."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user, get_current_user
from ...db.models import User
from ...db.session import get_db
from ...services.governance.content_moderator import moderate

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("/export/me")
async def export_my_data(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """GDPR Article 20 — export all data for the authenticated user."""
    from ...services.audit.audit_models import AuditEvent

    audit_rows = (await db.execute(
        select(AuditEvent)
        .where(AuditEvent.user_id == str(user.id))
        .order_by(AuditEvent.timestamp.desc())
        .limit(5000)
    )).scalars().all()

    payload = {
        "export_at": datetime.utcnow().isoformat(),
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": getattr(user, "email", None),
            "created_at": user.created_at.isoformat() if hasattr(user, "created_at") and user.created_at else None,
        },
        "audit_events": [
            {"timestamp": e.timestamp.isoformat(), "event_type": e.event_type,
             "action": e.action, "resource_type": e.resource_type,
             "request_path": e.request_path}
            for e in audit_rows
        ],
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([data]), media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=my_data_{user.username}.json"},
    )


class ModerateRequest(BaseModel):
    content: str
    context: str = "general"


@router.post("/moderate")
async def moderate_content(body: ModerateRequest, _admin: User = Depends(get_admin_user)):
    """Run content moderation check (admin only)."""
    return moderate(body.content)


@router.get("/admin/export/users")
async def export_user_list(
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    """CSV export of all users for compliance reporting."""
    users = (await db.execute(select(User))).scalars().all()
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=["id", "username", "is_admin", "is_active"])
    w.writeheader()
    for u in users:
        w.writerow({"id": str(u.id), "username": u.username,
                    "is_admin": u.is_admin, "is_active": u.is_active})
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=users_export.csv"})
