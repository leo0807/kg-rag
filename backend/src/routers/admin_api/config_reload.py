from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ...auth.deps import get_admin_user
from ...db.models import User
from ...core.config import (
    RELOADABLE_FIELDS,
    get_reloadable_settings_snapshot,
    reload_reloadable_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/config", tags=["admin"])


@router.get("")
async def get_config(_: User = Depends(get_admin_user)):
    return {
        "reloadable_fields": sorted(RELOADABLE_FIELDS),
        "config": get_reloadable_settings_snapshot(),
    }


_BREAKER_FIELDS = frozenset({"LLM_CIRCUIT_BREAKER_THRESHOLD", "LLM_CIRCUIT_BREAKER_RESET_SECONDS"})

_EMBEDDING_RESTART_REQUIRED_FIELDS = frozenset({
    "EMBEDDING_DEVICE",
    "REMOTE_EMBEDDING_BATCH_SIZE",
})


@router.post("/reload")
async def reload_config(_: User = Depends(get_admin_user)):
    changed = reload_reloadable_settings()
    if changed.keys() & _BREAKER_FIELDS:
        from ...services.ai.circuit_breaker import reset_circuit_breaker
        reset_circuit_breaker()
    for field in changed.keys() & _EMBEDDING_RESTART_REQUIRED_FIELDS:
        logger.warning(
            "%s changed but embedding service is a singleton; "
            "uvicorn restart required for new value to take effect",
            field,
        )
    return {
        "status": "ok",
        "changed": changed,
        "reloadable_fields": sorted(RELOADABLE_FIELDS),
        "config": get_reloadable_settings_snapshot(),
    }

