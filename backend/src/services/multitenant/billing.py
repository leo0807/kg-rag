"""
G5.3 账单生成服务
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.tenant_models import Bill, Plan, Subscription, Tenant, TenantUsage

logger = logging.getLogger(__name__)

_OVERAGE_RATE_PER_1K_TOKENS = Decimal("0.02")   # ¥0.02 / 1k tokens


def _last_month() -> str:
    now = datetime.utcnow()
    first_of_month = now.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    return last_month_end.strftime("%Y-%m")


async def _get_plan(db: AsyncSession, plan_name: str) -> Plan | None:
    return (
        await db.execute(select(Plan).where(Plan.name == plan_name))
    ).scalar_one_or_none()


async def _get_usage(db: AsyncSession, tenant_id: str, period: str) -> TenantUsage | None:
    return (
        await db.execute(
            select(TenantUsage).where(
                TenantUsage.tenant_id == tenant_id,
                TenantUsage.period == period,
            )
        )
    ).scalar_one_or_none()


def _calculate_bill(
    tenant: Tenant,
    plan: Plan | None,
    usage: TenantUsage | None,
    period: str,
) -> dict:
    base = plan.monthly_price_cny if plan and plan.monthly_price_cny else Decimal("0")
    overage = Decimal("0")

    if plan and usage and plan.max_llm_tokens_per_month:
        excess = max(0, usage.llm_tokens_used - plan.max_llm_tokens_per_month)
        overage = Decimal(excess // 1000) * _OVERAGE_RATE_PER_1K_TOKENS

    total = base + overage
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant.id,
        "billing_period": period,
        "base_amount": base,
        "overage_amount": overage,
        "discount": Decimal("0"),
        "total_amount": total,
        "status": "pending",
        "details": {
            "plan": tenant.plan,
            "base_price": str(base),
            "overage_tokens": usage.llm_tokens_used if usage else 0,
            "overage_cost": str(overage),
        },
    }


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_monthly_bills(self, period: str | None = None) -> list[dict]:
        """为所有活跃租户生成上月账单（幂等）。"""
        billing_period = period or _last_month()
        tenants = (
            await self.db.execute(
                select(Tenant).where(Tenant.status.in_(["active", "trial"]))
            )
        ).scalars().all()

        results = []
        for tenant in tenants:
            existing = (
                await self.db.execute(
                    select(Bill).where(
                        Bill.tenant_id == tenant.id,
                        Bill.billing_period == billing_period,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                logger.debug("租户 %s 账单已存在，跳过", tenant.id)
                continue

            plan = await _get_plan(self.db, tenant.plan)
            usage = await _get_usage(self.db, tenant.id, billing_period)

            bill_data = _calculate_bill(tenant, plan, usage, billing_period)
            bill = Bill(**bill_data)
            self.db.add(bill)
            results.append(bill_data)
            logger.info("生成账单: 租户=%s 金额=¥%s", tenant.name, bill_data["total_amount"])

        await self.db.commit()
        return results

    async def get_bills(self, tenant_id: str, limit: int = 12) -> list[Bill]:
        rows = (
            await self.db.execute(
                select(Bill)
                .where(Bill.tenant_id == tenant_id)
                .order_by(Bill.billing_period.desc())
                .limit(limit)
            )
        ).scalars().all()
        return list(rows)

    async def pay_bill(self, bill_id: str, tenant_id: str) -> Bill:
        bill = (
            await self.db.execute(
                select(Bill).where(Bill.id == bill_id, Bill.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not bill:
            from fastapi import HTTPException
            raise HTTPException(404, "账单不存在")
        bill.status = "paid"
        bill.paid_at = datetime.utcnow()
        await self.db.commit()
        return bill

    async def seed_plans(self) -> None:
        """初始化内置套餐（幂等）。"""
        built_in = [
            {"name": "free",       "display_name": "免费版",
             "max_users": 10,      "max_documents": 100,  "max_storage_mb": 5_000,
             "max_queries_per_month": 10_000, "max_llm_tokens_per_month": 5_000_000,
             "monthly_price_cny": 0, "yearly_price_cny": 0},
            {"name": "standard",   "display_name": "标准版",
             "max_users": 100,     "max_documents": 1_000, "max_storage_mb": 50_000,
             "max_queries_per_month": 100_000, "max_llm_tokens_per_month": 50_000_000,
             "monthly_price_cny": Decimal("999"), "yearly_price_cny": Decimal("9990")},
            {"name": "enterprise", "display_name": "企业版",
             "max_users": None,    "max_documents": None, "max_storage_mb": None,
             "max_queries_per_month": None, "max_llm_tokens_per_month": None,
             "monthly_price_cny": Decimal("9999"), "yearly_price_cny": Decimal("99990")},
        ]
        for p in built_in:
            existing = (await self.db.execute(select(Plan).where(Plan.name == p["name"]))).scalar_one_or_none()
            if existing:
                continue
            self.db.add(Plan(**p))
        await self.db.commit()
