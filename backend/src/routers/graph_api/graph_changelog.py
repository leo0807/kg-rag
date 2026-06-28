"""
Graph changelog and rollback API.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...core.security import get_current_admin_user
from ...services.graph.changelog import (
    get_changelog,
    get_incremental_sync,
    rollback_change,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/graph", tags=["graph-changelog"])


@router.get("/changelog")
async def list_changelog(
    since: Optional[str] = Query(None, description="ISO datetime filter"),
    operation_type: Optional[str] = Query(None),
    operator: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    _admin=Depends(get_current_admin_user),
):
    """Return graph change log with optional filters."""
    return await asyncio.to_thread(
        get_changelog, since, operation_type, operator, limit
    )


@router.get("/changelog/{change_id}")
async def get_change_detail(
    change_id: int,
    _admin=Depends(get_current_admin_user),
):
    """Return a single change record with before/after snapshot."""
    records = await asyncio.to_thread(get_changelog, None, None, None, 1000)
    match = next((r for r in records if r["id"] == change_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Change record not found")
    return match


class RollbackRequest(BaseModel):
    confirm: bool = False


@router.post("/changelog/{change_id}/rollback")
async def rollback(
    change_id: int,
    body: RollbackRequest,
    admin=Depends(get_current_admin_user),
):
    """Reverse a single graph change operation."""
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to proceed with rollback",
        )
    result = await asyncio.to_thread(
        rollback_change, change_id, str(admin.id)
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


@router.get("/incremental-sync")
async def incremental_sync(
    since: str = Query(..., description="ISO datetime for incremental pull"),
    format_type: str = Query("json", enum=["json"]),
):
    """
    Return graph changes as JSON Patch for downstream system sync (ERP/MES/PLM).
    Compatible with ETag-based incremental polling.
    """
    patches = await asyncio.to_thread(get_incremental_sync, since, format_type)
    return {"since": since, "patches": patches, "count": len(patches)}
