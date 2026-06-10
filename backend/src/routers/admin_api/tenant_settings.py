"""
G6.2 租户配置管理 API
GET  /api/admin/tenant-settings       — 查看当前租户配置
PUT  /api/admin/tenant-settings       — 更新当前租户配置
GET  /api/admin/tenant-settings/brand — 获取品牌配置（公开）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user, get_current_user
from ...db.models import User
from ...db.session import get_db
from ...db.tenant_models import Tenant
from ...services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(prefix="/api/admin/tenant-settings", tags=["tenant-settings"])


class BrandSettings(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None   # e.g. "#3b82f6"
    app_title: str | None = None
    favicon_url: str | None = None


class NotificationSettings(BaseModel):
    email_enabled: bool = True
    quota_alert_pct: int = 80           # 触发告警的配额使用百分比


class AdvancedSettings(BaseModel):
    default_strategy: str = "parallel"
    default_language: str = "zh-CN"
    default_timezone: str = "Asia/Shanghai"
    llm_model_override: str | None = None   # 企业版专属
    sso_enabled: bool = False
    sso_provider: str | None = None
    custom_domain: str | None = None


class TenantSettingsUpdate(BaseModel):
    brand: BrandSettings | None = None
    notifications: NotificationSettings | None = None
    advanced: AdvancedSettings | None = None


async def _get_tenant(db: AsyncSession, tenant_id: str) -> Tenant:
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "租户不存在")
    return t


@router.get("")
async def get_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    tenant_id = get_tenant_id_optional(request)
    if not tenant_id:
        raise HTTPException(403, "无租户上下文")
    t = await _get_tenant(db, tenant_id)
    settings = t.settings or {}
    return {
        "brand": settings.get("brand", {}),
        "notifications": settings.get("notifications", {}),
        "advanced": settings.get("advanced", {}),
        "plan": t.plan,
    }


@router.put("")
async def update_settings(
    body: TenantSettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    tenant_id = get_tenant_id_optional(request)
    if not tenant_id:
        raise HTTPException(403, "无租户上下文")
    t = await _get_tenant(db, tenant_id)
    settings: dict = dict(t.settings or {})

    if body.brand:
        settings["brand"] = body.brand.model_dump(exclude_none=True)
    if body.notifications:
        settings["notifications"] = body.notifications.model_dump()
    if body.advanced:
        adv = body.advanced.model_dump(exclude_none=True)
        # 企业版限定字段
        if t.plan != "enterprise":
            adv.pop("llm_model_override", None)
            adv.pop("sso_enabled", None)
            adv.pop("sso_provider", None)
            adv.pop("custom_domain", None)
        settings["advanced"] = adv

    t.settings = settings
    await db.commit()
    return {"ok": True, "settings": settings}


@router.get("/brand")
async def get_brand(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """公开接口，用于前端加载动态品牌配置。"""
    tenant_id = get_tenant_id_optional(request)
    if not tenant_id:
        return {}
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        return {}
    settings = t.settings or {}
    brand = settings.get("brand", {})
    return {
        "logo_url": brand.get("logo_url"),
        "primary_color": brand.get("primary_color", "#3b82f6"),
        "app_title": brand.get("app_title", "CPS 知识库"),
        "tenant_name": t.name,
    }
