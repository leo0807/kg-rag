"""
G5.4 账单 API
GET  /api/admin/billing/bills        — 账单列表
GET  /api/admin/billing/bills/{id}   — 账单详情
POST /api/admin/billing/bills/{id}/pay — 支付（占位）
GET  /api/admin/billing/plans        — 套餐列表
POST /api/platform/billing/generate  — 平台超管触发账单生成
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user, get_current_user
from ...db.models import User
from ...db.session import get_db
from ...db.tenant_models import Bill, Plan
from ...services.multitenant.billing import BillingService
from ...services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(tags=["billing"])


def _bill_dict(b: Bill) -> dict:
    return {
        "id": b.id, "tenant_id": b.tenant_id, "billing_period": b.billing_period,
        "base_amount": str(b.base_amount), "overage_amount": str(b.overage_amount),
        "discount": str(b.discount), "total_amount": str(b.total_amount),
        "status": b.status, "details": b.details,
        "paid_at": b.paid_at.isoformat() if b.paid_at else None,
        "created_at": b.created_at.isoformat(),
    }


@router.get("/api/admin/billing/bills")
async def list_bills(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    tenant_id = get_tenant_id_optional(request)
    if not tenant_id:
        raise HTTPException(403, "无租户上下文")
    svc = BillingService(db)
    bills = await svc.get_bills(tenant_id)
    return [_bill_dict(b) for b in bills]


@router.get("/api/admin/billing/bills/{bill_id}")
async def get_bill(
    bill_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    tenant_id = get_tenant_id_optional(request)
    bill = (
        await db.execute(select(Bill).where(Bill.id == bill_id, Bill.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not bill:
        raise HTTPException(404, "账单不存在")
    return _bill_dict(bill)


@router.post("/api/admin/billing/bills/{bill_id}/pay")
async def pay_bill(
    bill_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    tenant_id = get_tenant_id_optional(request)
    svc = BillingService(db)
    bill = await svc.pay_bill(bill_id, tenant_id)
    return _bill_dict(bill)


@router.get("/api/admin/billing/plans")
async def list_plans(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    plans = (await db.execute(select(Plan).where(Plan.is_active))).scalars().all()
    return [
        {
            "id": p.id, "name": p.name, "display_name": p.display_name,
            "max_users": p.max_users, "max_documents": p.max_documents,
            "max_storage_mb": p.max_storage_mb,
            "max_queries_per_month": p.max_queries_per_month,
            "max_llm_tokens_per_month": p.max_llm_tokens_per_month,
            "features": p.features,
            "monthly_price_cny": str(p.monthly_price_cny) if p.monthly_price_cny else "0",
            "yearly_price_cny": str(p.yearly_price_cny) if p.yearly_price_cny else "0",
        }
        for p in plans
    ]


@router.post("/api/platform/billing/generate")
async def generate_bills(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_platform_admin:
        raise HTTPException(403, "需要平台超管权限")
    svc = BillingService(db)
    results = await svc.generate_monthly_bills()
    return {"generated": len(results), "bills": results}
