"""
I8: Admin API for fine-tuning job management.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.deployment_models import FinetuneJob
from ...db.models import User
from ...db.session import get_db
from ...services.ai.finetuner import Finetuner, FinetuneConfig, finetuner
from ...services.ai.finetune_data_collector import finetune_data_collector

router = APIRouter(prefix="/api/admin/finetune", tags=["admin-finetune"])


class JobCreate(BaseModel):
    name: str
    base_model: str
    dataset_path: str = ""
    method: str = "lora"
    learning_rate: float = 2e-4
    epochs: int = 3
    batch_size: int = 4
    auto_collect: bool = False   # collect data from feedback before training
    collect_format: str = "alpaca"


@router.get("")
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> List[Dict[str, Any]]:
    from sqlalchemy import select
    rows = (await db.execute(
        select(FinetuneJob).order_by(FinetuneJob.created_at.desc())
    )).scalars().all()
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]


@router.post("")
async def create_job(
    body: JobCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    dataset_path = body.dataset_path

    if body.auto_collect:
        export_path = f"/tmp/finetune_data_{body.name}.json"
        result = await finetune_data_collector.export_for_finetuning(
            db, export_path, fmt=body.collect_format
        )
        dataset_path = result["path"]

    if not dataset_path:
        raise HTTPException(status_code=400, detail="dataset_path 必须提供，或启用 auto_collect")

    config = FinetuneConfig(
        name=body.name,
        base_model=body.base_model,
        dataset_path=dataset_path,
        method=body.method,
        learning_rate=body.learning_rate,
        epochs=body.epochs,
        batch_size=body.batch_size,
    )
    return await finetuner.start_job(db, config)


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    try:
        return await finetuner.get_progress(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    return await finetuner.cancel(job_id)


@router.post("/{job_id}/deploy")
async def deploy_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    try:
        return await finetuner.deploy_model(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"部署失败: {e}")


@router.post("/export-data")
async def export_training_data(
    format: str = "alpaca",
    min_rating: int = 4,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Collect and export training data from feedback/eval."""
    import time
    path = f"/tmp/finetune_export_{int(time.time())}.json"
    return await finetune_data_collector.export_for_finetuning(
        db, path, fmt=format, min_rating=min_rating
    )
