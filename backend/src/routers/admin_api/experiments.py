"""Admin API — A/B experiment CRUD + results"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import User
from ...db.session import get_db
from ...db.ux_models import Experiment

router = APIRouter(prefix="/api/admin/experiments", tags=["admin-experiments"])


class VariantIn(BaseModel):
    name: str
    weight: int


class ExperimentIn(BaseModel):
    name: str
    description: str = ""
    variants: list[VariantIn]
    status: str = "active"


@router.get("")
async def list_experiments(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Experiment).order_by(Experiment.created_at.desc()))).scalars().all()
    return [
        {
            "id": r.id, "name": r.name, "description": r.description,
            "variants": r.variants, "metrics": r.metrics,
            "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("")
async def create_experiment(
    body: ExperimentIn,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    total_weight = sum(v.weight for v in body.variants)
    if total_weight != 100:
        raise HTTPException(400, f"Variant weights must sum to 100 (got {total_weight})")

    exp = Experiment(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        variants=[v.model_dump() for v in body.variants],
        status=body.status,
    )
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    return {"id": exp.id}


@router.put("/{exp_id}/status")
async def set_status(
    exp_id: str,
    status: str,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Experiment, exp_id)
    if not row:
        raise HTTPException(404, "experiment not found")
    if status not in ("active", "paused", "archived"):
        raise HTTPException(400, "invalid status")
    row.status = status
    await db.commit()
    return {"ok": True}


@router.get("/{exp_id}/results")
async def get_results(
    exp_id: str,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Experiment, exp_id)
    if not row:
        raise HTTPException(404, "experiment not found")
    return {"id": exp_id, "name": row.name, "metrics": row.metrics or {}}


@router.delete("/{exp_id}")
async def delete_experiment(
    exp_id: str,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(Experiment).where(Experiment.id == exp_id))
    await db.commit()
    return {"ok": True}
