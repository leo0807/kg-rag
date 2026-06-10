"""
G3.1 平台管理员租户 CRUD
POST/GET/PUT/DELETE /api/platform/tenants
POST /api/platform/tenants/{id}/suspend|resume|extend
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_current_user
from ...db.models import User
from ...db.session import get_db
from ...db.tenant_models import DEFAULT_TENANT_ID, Tenant, TenantQuota

router = APIRouter(prefix="/api/platform/tenants", tags=["platform-tenants"])


def _require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="需要平台超管权限")
    return user


class TenantCreate(BaseModel):
    name: str
    slug: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    plan: str = "free"
    status: str = "active"
    settings: dict = {}


class TenantUpdate(BaseModel):
    name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    plan: str | None = None
    status: str | None = None
    settings: dict | None = None


class ExtendRequest(BaseModel):
    days: int = 30


def _tenant_dict(t: Tenant) -> dict:
    return {
        "id": t.id, "name": t.name, "slug": t.slug,
        "contact_name": t.contact_name, "contact_email": t.contact_email,
        "contact_phone": t.contact_phone, "status": t.status, "plan": t.plan,
        "trial_ends_at": t.trial_ends_at.isoformat() if t.trial_ends_at else None,
        "subscription_ends_at": t.subscription_ends_at.isoformat() if t.subscription_ends_at else None,
        "created_at": t.created_at.isoformat(), "settings": t.settings,
    }


@router.get("")
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    rows = (await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))).scalars().all()
    return [_tenant_dict(t) for t in rows]


@router.post("", status_code=201)
async def create_tenant(
    body: TenantCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    existing = (await db.execute(select(Tenant).where(Tenant.slug == body.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "slug 已存在")

    tenant = Tenant(
        id=str(uuid.uuid4()), name=body.name, slug=body.slug,
        contact_name=body.contact_name, contact_email=body.contact_email,
        contact_phone=body.contact_phone, plan=body.plan, status=body.status,
        settings=body.settings,
    )
    db.add(tenant)

    quota = TenantQuota(tenant_id=tenant.id)
    db.add(quota)

    await db.commit()
    await db.refresh(tenant)
    return _tenant_dict(tenant)


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "租户不存在")
    return _tenant_dict(t)


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    body: TenantUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "租户不存在")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(t, field, val)
    await db.commit()
    await db.refresh(t)
    return _tenant_dict(t)


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    if tenant_id == DEFAULT_TENANT_ID:
        raise HTTPException(400, "不能删除默认租户")
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "租户不存在")
    t.status = "suspended"
    await db.commit()
    return {"ok": True, "message": "租户已停用"}


@router.post("/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404)
    t.status = "suspended"
    await db.commit()
    return {"ok": True}


@router.post("/{tenant_id}/resume")
async def resume_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404)
    t.status = "active"
    await db.commit()
    return {"ok": True}


@router.post("/{tenant_id}/extend")
async def extend_tenant(
    tenant_id: str,
    body: ExtendRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform_admin),
):
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404)
    base = t.subscription_ends_at or datetime.utcnow()
    t.subscription_ends_at = base + timedelta(days=body.days)
    t.status = "active"
    await db.commit()
    return {"ok": True, "subscription_ends_at": t.subscription_ends_at.isoformat()}
