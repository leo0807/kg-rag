"""
G8 平台运维工具
POST /api/platform/tenants/{id}/export   — 导出租户数据
GET  /api/platform/tenants/{id}/health   — 租户健康检查
POST /api/platform/tenants/{id}/clone    — 克隆租户配置
GET  /api/platform/dashboard             — 平台总仪表盘
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_current_user
from ...db.models import Conversation, User
from ...db.session import get_db
from ...db.tenant_models import DEFAULT_TENANT_ID, Tenant, TenantQuota, TenantUsage

router = APIRouter(prefix="/api/platform", tags=["platform-ops"])
logger = logging.getLogger(__name__)


def _require_platform(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(403, "需要平台超管权限")
    return user


@router.get("/tenants/{tenant_id}/health")
async def tenant_health(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform),
):
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404)

    period = datetime.utcnow().strftime("%Y-%m")
    usage = (
        await db.execute(
            select(TenantUsage).where(
                TenantUsage.tenant_id == tenant_id, TenantUsage.period == period
            )
        )
    ).scalar_one_or_none()
    quota = (
        await db.execute(select(TenantQuota).where(TenantQuota.tenant_id == tenant_id))
    ).scalar_one_or_none()

    user_count = (
        await db.execute(select(func.count(User.id)).where(User.tenant_id == tenant_id))
    ).scalar() or 0

    # 近 7 天活跃对话数
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_convs = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.tenant_id == tenant_id,
                Conversation.updated_at >= week_ago,
            )
        )
    ).scalar() or 0

    u = usage or TenantUsage(tenant_id=tenant_id, period=period)
    q = quota or TenantQuota(tenant_id=tenant_id)

    def score() -> int:
        s = 100
        if t.status != "active":
            s -= 40
        if q.max_queries_per_month and u.queries_count >= q.max_queries_per_month * 0.9:
            s -= 20
        if q.max_storage_mb and u.storage_used_mb >= q.max_storage_mb * 0.9:
            s -= 15
        if t.subscription_ends_at and t.subscription_ends_at < datetime.utcnow() + timedelta(days=7):
            s -= 10
        return max(0, s)

    return {
        "tenant_id": tenant_id,
        "tenant_name": t.name,
        "status": t.status,
        "health_score": score(),
        "users": {"count": user_count, "limit": q.max_users},
        "documents": {"count": u.documents_count, "limit": q.max_documents},
        "queries_this_month": {"count": u.queries_count, "limit": q.max_queries_per_month},
        "active_conversations_7d": recent_convs,
        "subscription_ends_at": t.subscription_ends_at.isoformat() if t.subscription_ends_at else None,
        "expires_soon": bool(
            t.subscription_ends_at and t.subscription_ends_at < datetime.utcnow() + timedelta(days=14)
        ),
    }


@router.post("/tenants/{tenant_id}/export")
async def export_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform),
):
    t = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404)

    users = (
        await db.execute(select(User).where(User.tenant_id == tenant_id))
    ).scalars().all()
    convs = (
        await db.execute(select(Conversation).where(Conversation.tenant_id == tenant_id))
    ).scalars().all()

    payload = {
        "export_time": datetime.utcnow().isoformat(),
        "tenant": {"id": t.id, "name": t.name, "slug": t.slug, "plan": t.plan, "settings": t.settings},
        "users": [{"id": u.id, "username": u.username, "email": u.email, "full_name": u.full_name} for u in users],
        "conversations_count": len(convs),
    }
    return JSONResponse(content=payload, headers={
        "Content-Disposition": f'attachment; filename="tenant-{t.slug}-export.json"'
    })


class CloneRequest(BaseModel):
    new_name: str
    new_slug: str


@router.post("/tenants/{tenant_id}/clone")
async def clone_tenant(
    tenant_id: str,
    body: CloneRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform),
):
    src = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not src:
        raise HTTPException(404)
    import uuid
    new_tenant = Tenant(
        id=str(uuid.uuid4()), name=body.new_name, slug=body.new_slug,
        plan=src.plan, status="active", settings=dict(src.settings or {}),
    )
    db.add(new_tenant)

    src_quota = (
        await db.execute(select(TenantQuota).where(TenantQuota.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if src_quota:
        new_quota = TenantQuota(
            tenant_id=new_tenant.id,
            max_users=src_quota.max_users,
            max_documents=src_quota.max_documents,
            max_storage_mb=src_quota.max_storage_mb,
            max_queries_per_month=src_quota.max_queries_per_month,
            max_llm_tokens_per_month=src_quota.max_llm_tokens_per_month,
            features=dict(src_quota.features or {}),
        )
        db.add(new_quota)

    await db.commit()
    return {"ok": True, "new_tenant_id": new_tenant.id}


@router.get("/dashboard")
async def platform_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform),
):
    total_tenants = (await db.execute(select(func.count(Tenant.id)))).scalar() or 0
    active = (await db.execute(select(func.count(Tenant.id)).where(Tenant.status == "active"))).scalar() or 0
    suspended = (await db.execute(select(func.count(Tenant.id)).where(Tenant.status == "suspended"))).scalar() or 0
    trial = (await db.execute(select(func.count(Tenant.id)).where(Tenant.status == "trial"))).scalar() or 0

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    period = datetime.utcnow().strftime("%Y-%m")
    total_queries = (
        await db.execute(
            select(func.sum(TenantUsage.queries_count)).where(TenantUsage.period == period)
        )
    ).scalar() or 0

    expiring_soon = (
        await db.execute(
            select(Tenant).where(
                Tenant.subscription_ends_at <= datetime.utcnow() + timedelta(days=14),
                Tenant.status == "active",
            )
        )
    ).scalars().all()

    return {
        "tenants": {"total": total_tenants, "active": active, "suspended": suspended, "trial": trial},
        "total_users": total_users,
        "queries_this_month": total_queries,
        "expiring_soon": [{"id": t.id, "name": t.name, "ends_at": t.subscription_ends_at.isoformat()} for t in expiring_soon],
        "generated_at": datetime.utcnow().isoformat(),
    }
