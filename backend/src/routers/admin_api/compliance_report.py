"""F7 — Compliance report API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import User
from ...db.session import get_db
from ...services.governance.compliance_report import generate_report, detect_anomalies

router = APIRouter(prefix="/api/admin/compliance", tags=["admin-compliance"])


@router.get("/report")
async def get_report(
    days: int = 30,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    return await generate_report(db, days=max(1, min(days, 365)))


@router.get("/anomalies")
async def get_anomalies(
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    return {"anomalies": await detect_anomalies(db)}
