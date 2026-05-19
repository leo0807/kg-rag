from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auth.deps import get_admin_user
from ...db.models import User
from ...core.config import (
    RELOADABLE_FIELDS,
    get_reloadable_settings_snapshot,
    reload_reloadable_settings,
)

router = APIRouter(prefix="/api/admin/config", tags=["admin"])


@router.get("")
async def get_config(_: User = Depends(get_admin_user)):
    return {
        "reloadable_fields": sorted(RELOADABLE_FIELDS),
        "config": get_reloadable_settings_snapshot(),
    }


@router.post("/reload")
async def reload_config(_: User = Depends(get_admin_user)):
    changed = reload_reloadable_settings()
    return {
        "status": "ok",
        "changed": changed,
        "reloadable_fields": sorted(RELOADABLE_FIELDS),
        "config": get_reloadable_settings_snapshot(),
    }

