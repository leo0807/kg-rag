"""J3.3: Admin API for custom report management."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_current_user
from ...db.models import User
from ...db.report_models import CustomReport, ReportSnapshot
from ...db.session import get_db
from ...services.analytics.report_engine import report_engine

router = APIRouter(prefix="/api/admin/reports", tags=["admin-reports"])


class ReportCreate(BaseModel):
    name: str
    description: str = ""
    config: Dict[str, Any] = {}
    layout: Dict[str, Any] = {}
    filters: Dict[str, Any] = {}
    is_public: bool = False
    schedule: Dict[str, Any] = {}
    recipients: List[str] = []


class ReportUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    schedule: Optional[Dict[str, Any]] = None
    recipients: Optional[List[str]] = None


def _row(r: CustomReport) -> Dict[str, Any]:
    return {c.name: getattr(r, c.name) for c in r.__table__.columns}


@router.get("")
async def list_reports(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    q = select(CustomReport).where(
        (CustomReport.owner_id == str(user.id)) | (CustomReport.is_public == True)
    ).order_by(CustomReport.created_at.desc())
    rows = (await db.execute(q)).scalars().all()
    return [_row(r) for r in rows]


@router.post("")
async def create_report(
    body: ReportCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    r = CustomReport(
        id=str(uuid.uuid4()),
        owner_id=str(user.id),
        tenant_id=str(getattr(user, "tenant_id", "") or ""),
        **body.model_dump(),
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _row(r)


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="报表不存在")
    return _row(r)


@router.put("/{report_id}")
async def update_report(
    report_id: str,
    body: ReportUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="报表不存在")
    if r.owner_id != str(user.id) and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="无权修改此报表")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(r, k, v)
    await db.commit()
    await db.refresh(r)
    return _row(r)


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="报表不存在")
    await db.delete(r)
    await db.commit()
    return {"deleted": report_id}


@router.post("/{report_id}/run")
async def run_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="报表不存在")

    configs = r.config if isinstance(r.config, list) else [r.config]
    results = []
    for cfg in configs:
        data = await report_engine.query(cfg, db)
        viz = report_engine.recommend_viz(data.get("rows", []), cfg)
        results.append({**data, "viz_type": viz})

    snap = ReportSnapshot(id=str(uuid.uuid4()), report_id=report_id, data={"results": results})
    db.add(snap)
    await db.commit()
    return {"report_id": report_id, "results": results, "snapshot_id": snap.id}


@router.post("/{report_id}/export")
async def export_report(
    report_id: str,
    fmt: str = "json",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    r = (await db.execute(select(CustomReport).where(CustomReport.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="报表不存在")

    from ...services.analytics.pdf_report import pdf_generator
    async def _gen():
        cfg = r.config if isinstance(r.config, list) else [r.config]
        data_list = [await report_engine.query(c, db) for c in cfg]
        path = await pdf_generator.generate(r.name, data_list, fmt=fmt)
        snap = ReportSnapshot(id=str(uuid.uuid4()), report_id=report_id,
                              data={}, file_path=path)
        db.add(snap)
        await db.commit()

    background_tasks.add_task(_gen)
    return {"status": "generating", "format": fmt}
