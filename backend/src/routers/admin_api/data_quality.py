"""F5 — Data quality monitoring API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import User
from ...db.session import get_db
from ...services.governance.data_quality import get_quality_summary

router = APIRouter(prefix="/api/admin/data-quality", tags=["admin-data-quality"])


@router.get("/summary")
async def quality_summary(
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    return await get_quality_summary(db)
