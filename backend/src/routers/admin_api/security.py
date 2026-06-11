"""
I5.3: Admin API for key management (super_admin only).
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...auth.deps import get_current_user
from ...db.models import User
from ...services.security.key_manager import key_manager

router = APIRouter(prefix="/api/admin/security", tags=["admin-security"])


def _require_super_admin(user: User = Depends(get_current_user)) -> User:
    if getattr(user, "role", None) != "super_admin":
        raise HTTPException(status_code=403, detail="需要 super_admin 权限")
    return user


class GenerateKeyRequest(BaseModel):
    name: str
    length: int = 32


class RotateKeyRequest(BaseModel):
    new_value: str = ""  # empty → auto-generate


@router.get("/keys")
async def list_keys(user: User = Depends(_require_super_admin)) -> List[str]:
    return await key_manager.list_keys()


@router.post("/keys/generate")
async def generate_key(
    body: GenerateKeyRequest,
    user: User = Depends(_require_super_admin),
) -> Dict[str, Any]:
    await key_manager.generate_random_key(body.name, body.length)
    return {"name": body.name, "generated": True}


@router.post("/keys/{key_name}/rotate")
async def rotate_key(
    key_name: str,
    body: RotateKeyRequest = RotateKeyRequest(),
    user: User = Depends(_require_super_admin),
) -> Dict[str, Any]:
    import base64
    import os
    new_value = body.new_value or base64.b64encode(os.urandom(32)).decode()
    await key_manager.rotate_key(key_name, new_value, actor=str(user.id))
    return {"name": key_name, "rotated": True}


@router.get("/keys/audit")
async def audit_log(
    key_name: str | None = None,
    user: User = Depends(_require_super_admin),
) -> List[Dict[str, Any]]:
    return key_manager.audit_log(key_name)


# ── I6.4: 等保合规检查 ────────────────────────────────────────────────────────

from ...auth.deps import get_admin_user  # noqa: E402


@router.get("/compliance")
async def compliance_check(_: User = Depends(get_admin_user)) -> Dict[str, Any]:
    """Run 等保2.0 compliance checks and return scored report."""
    from ...services.security.compliance_checker import compliance_checker
    report = await compliance_checker.run_check()
    return report.to_dict()
