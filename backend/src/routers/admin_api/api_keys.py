"""
H7.1 API Key 管理 API
POST   /api/admin/api-keys        — 创建
GET    /api/admin/api-keys        — 列表
DELETE /api/admin/api-keys/{id}   — 删除
GET    /api/admin/api-keys/{id}/usage — 使用统计
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_current_user
from ...db.integration_models import ApiKey, ApiKeyUsage
from ...db.models import User
from ...db.session import get_db
from ...services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(prefix="/api/admin/api-keys", tags=["api-keys"])

_PREFIX = "kg_"
_SCOPES = ["query:read", "documents:read", "feedback:write", "admin:read"]


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["query:read"]
    allowed_ips: list[str] = []
    rate_limit: int = 60
    expires_at: str | None = None  # ISO date string


def _row(k: ApiKey, show_prefix_only: bool = True) -> dict:
    return {
        "id": k.id, "name": k.name,
        "key_prefix": k.key_prefix,
        "scopes": k.scopes, "allowed_ips": k.allowed_ips,
        "rate_limit": k.rate_limit, "is_active": k.is_active,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "created_at": k.created_at.isoformat(),
    }


@router.get("")
async def list_keys(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tid = get_tenant_id_optional(request)
    stmt = select(ApiKey).where(ApiKey.user_id == user.id)
    if tid:
        stmt = stmt.where(ApiKey.tenant_id == tid)
    rows = (await db.execute(stmt.order_by(ApiKey.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_key(
    body: ApiKeyCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invalid = [s for s in body.scopes if s not in _SCOPES]
    if invalid:
        raise HTTPException(400, f"未知 scope: {invalid}")

    raw_key = _PREFIX + secrets.token_urlsafe(32)
    prefix  = raw_key[:12] + "…"
    expires = datetime.fromisoformat(body.expires_at) if body.expires_at else None

    tid = get_tenant_id_optional(request)
    obj = ApiKey(
        id=str(uuid.uuid4()), tenant_id=tid, user_id=user.id,
        name=body.name, key_prefix=prefix, key_hash=_hash(raw_key),
        scopes=body.scopes, allowed_ips=body.allowed_ips,
        rate_limit=body.rate_limit, expires_at=expires,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)

    resp = _row(obj)
    resp["api_key"] = raw_key   # 仅创建时返回完整密钥
    return resp


@router.delete("/{key_id}")
async def delete_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    obj = (await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )).scalar_one_or_none()
    if not obj:
        raise HTTPException(404)
    await db.delete(obj)
    await db.commit()
    return {"ok": True}


@router.get("/{key_id}/usage")
async def key_usage(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = (await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )).scalar_one_or_none()
    if not key:
        raise HTTPException(404)

    total = (await db.execute(
        select(func.count(ApiKeyUsage.id)).where(ApiKeyUsage.api_key_id == key_id)
    )).scalar() or 0

    recent = (await db.execute(
        select(ApiKeyUsage)
        .where(ApiKeyUsage.api_key_id == key_id)
        .order_by(ApiKeyUsage.created_at.desc())
        .limit(20)
    )).scalars().all()

    return {
        "total_calls": total,
        "recent": [
            {"endpoint": r.endpoint, "status_code": r.status_code,
             "duration_ms": r.duration_ms, "created_at": r.created_at.isoformat()}
            for r in recent
        ],
    }


@router.get("/scopes")
async def list_scopes(_: User = Depends(get_current_user)):
    return _SCOPES
