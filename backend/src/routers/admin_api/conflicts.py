from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User
from ...db.session import get_db
from ...services.quality.conflict_detector import (
    get_conflict_stats,
    get_scan,
    list_conflicts,
    list_scans,
    start_conflict_scan,
    update_conflict_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/conflicts", tags=["admin"])


class StatusUpdate(BaseModel):
    status: str


# ── Scan management ───────────────────────────────────────────────────────────

@router.post("/scan")
async def trigger_scan(
    entity_limit: int = Query(60, ge=5, le=300),
    constraint_limit: int = Query(200, ge=10, le=1000),
    driver=Depends(get_driver),
    _: User = Depends(get_admin_user),
):
    return await start_conflict_scan(
        driver=driver,
        entity_limit=entity_limit,
        constraint_limit=constraint_limit,
    )


@router.get("/scan/{scan_id}")
async def get_scan_status(
    scan_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        return get_scan(scan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="扫描任务不存在")


@router.get("/scans")
async def list_scan_history(
    limit: int = Query(10, ge=1, le=50),
    _: User = Depends(get_admin_user),
):
    return list_scans(limit)


# ── Conflict records ──────────────────────────────────────────────────────────

@router.get("")
async def get_conflicts(
    status: Optional[str] = Query(None),
    conflict_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    scan_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await list_conflicts(
        db,
        status=status,
        conflict_type=conflict_type,
        severity=severity,
        scan_id=scan_id,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "items": [
            {
                "id": r.id,
                "scan_id": r.scan_id,
                "conflict_type": r.conflict_type,
                "severity": r.severity,
                "entity_name": r.entity_name,
                "entity_type": r.entity_type,
                "section_a_chunk_id": r.section_a_chunk_id,
                "section_a_doc_id": r.section_a_doc_id,
                "section_a_title": r.section_a_title,
                "section_a_snippet": r.section_a_snippet,
                "section_b_chunk_id": r.section_b_chunk_id,
                "section_b_doc_id": r.section_b_doc_id,
                "section_b_title": r.section_b_title,
                "section_b_snippet": r.section_b_snippet,
                "description": r.description,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/stats")
async def get_stats(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_conflict_stats(db)


@router.patch("/{conflict_id}/status")
async def patch_conflict_status(
    conflict_id: int,
    body: StatusUpdate,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        record = await update_conflict_status(db, conflict_id, body.status)
    except KeyError:
        raise HTTPException(status_code=404, detail="冲突记录不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": record.id, "status": record.status}
