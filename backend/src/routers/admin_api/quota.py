"""
G4.4 配额管理 API
GET  /api/admin/quota         — 当前租户用量
PUT  /api/platform/quota/{id} — 平台管理员修改配额
GET  /api/platform/usage      — 全租户用量（平台管理员）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user, get_current_user
from ...db.models import User
from ...db.session import get_db
from ...db.tenant_models import Tenant, TenantQuota, TenantUsage
from ...services.multitenant.quota_checker import get_tenant_usage_summary
from ...services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(tags=["quota"])


@router.get("/api/admin/quota")
async def my_quota(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    tenant_id = get_tenant_id_optional(request)
    if not tenant_id:
        raise HTTPException(403, "无租户上下文")
    return await get_tenant_usage_summary(db, tenant_id)


class QuotaUpdate(BaseModel):
    max_users: int | None = None
    max_documents: int | None = None
    max_storage_mb: int | None = None
    max_queries_per_month: int | None = None
    max_llm_tokens_per_month: int | None = None
    max_evals_per_month: int | None = None
    rate_limit_per_minute: int | None = None
    rate_limit_per_hour: int | None = None
    features: dict | None = None


@router.put("/api/platform/quota/{tenant_id}")
async def update_quota(
    tenant_id: str,
    body: QuotaUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_platform_admin:
        raise HTTPException(403, "需要平台超管权限")

    quota = (
        await db.execute(select(TenantQuota).where(TenantQuota.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if quota is None:
        quota = TenantQuota(tenant_id=tenant_id)
        db.add(quota)

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(quota, field, val)
    await db.commit()
    return {"ok": True}


@router.get("/api/platform/usage")
async def all_usage(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_platform_admin:
        raise HTTPException(403, "需要平台超管权限")

    tenants = (await db.execute(select(Tenant))).scalars().all()
    result = []
    for t in tenants:
        summary = await get_tenant_usage_summary(db, t.id)
        result.append({"tenant_id": t.id, "tenant_name": t.name, **summary})
    return result
