"""F3.3 — Admin API for data retention policy management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.lifecycle_models import DataRetentionPolicy
from ...db.models import User
from ...db.session import get_db
from ...services.governance.lifecycle_runner import run_lifecycle

router = APIRouter(prefix="/api/admin/lifecycle", tags=["admin-lifecycle"])


def _fmt(p: DataRetentionPolicy) -> dict:
    return {
        "id": p.id, "resource_type": p.resource_type,
        "retention_days": p.retention_days,
        "archive_before_delete": p.archive_before_delete,
        "is_active": p.is_active,
        "last_run_at": p.last_run_at.isoformat() if p.last_run_at else None,
        "last_run_deleted": p.last_run_deleted,
    }


@router.get("/policies")
async def list_policies(
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    rows = (await db.execute(select(DataRetentionPolicy))).scalars().all()
    return [_fmt(r) for r in rows]


class PolicyUpdate(BaseModel):
    retention_days: int
    is_active: bool
    archive_before_delete: bool = False


@router.put("/policies/{policy_id}")
async def update_policy(
    policy_id: str, body: PolicyUpdate,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    p = await db.get(DataRetentionPolicy, policy_id)
    if not p:
        raise HTTPException(404, "策略不存在")
    if body.retention_days < 1:
        raise HTTPException(400, "保留天数至少为 1")
    p.retention_days = body.retention_days
    p.is_active = body.is_active
    p.archive_before_delete = body.archive_before_delete
    await db.commit()
    return _fmt(p)


@router.post("/run")
async def trigger_lifecycle(
    _admin: User = Depends(get_admin_user),
):
    """Manually trigger lifecycle runner."""
    results = await run_lifecycle()
    return {"results": results}
