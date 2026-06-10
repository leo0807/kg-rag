"""
G1.1 / G4.1 / G5.1 / G5.2 多租户核心数据模型
Tenant / TenantQuota / TenantUsage / Plan / Subscription / Bill
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as PGJSON
except ImportError:
    from sqlalchemy import JSON as PGJSON  # type: ignore[assignment]


def _uuid() -> str:
    return str(uuid.uuid4())

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# ──────────────────────────── G1.1 租户 ────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        Index("idx_tenant_slug",   "slug"),
        Index("idx_tenant_status", "status"),
    )

    id:           Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    name:         Mapped[str]      = mapped_column(String(200), nullable=False)
    slug:         Mapped[str]      = mapped_column(String(100), unique=True, nullable=False)

    contact_name:  Mapped[str | None] = mapped_column(String(100),  nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200),  nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50),   nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="active")  # active/suspended/expired/trial
    plan:   Mapped[str] = mapped_column(String(50), default="free")    # free/standard/enterprise

    trial_ends_at:        Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at:           Mapped[datetime]         = mapped_column(DateTime, server_default=func.now())
    updated_at:           Mapped[datetime]         = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    settings: Mapped[Any] = mapped_column(PGJSON, default=dict)
    metadata_: Mapped[Any] = mapped_column(PGJSON, default=dict, name="tenant_metadata")


# ──────────────────────────── G4.1 配额 / 用量 ────────────────────────────

_DEFAULT_FEATURES = {
    "agent_mode": True,
    "multi_hop": True,
    "spec_generation": False,
    "evaluation": True,
    "advanced_search": True,
}


class TenantQuota(Base):
    __tablename__ = "tenant_quotas"

    tenant_id: Mapped[str] = mapped_column(String(36), primary_key=True)

    max_users:               Mapped[int] = mapped_column(Integer, default=10)
    max_documents:           Mapped[int] = mapped_column(Integer, default=100)
    max_storage_mb:          Mapped[int] = mapped_column(Integer, default=5000)

    max_queries_per_month:     Mapped[int] = mapped_column(Integer, default=10_000)
    max_llm_tokens_per_month:  Mapped[int] = mapped_column(Integer, default=5_000_000)
    max_evals_per_month:       Mapped[int] = mapped_column(Integer, default=50)

    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    rate_limit_per_hour:   Mapped[int] = mapped_column(Integer, default=1000)

    features:   Mapped[Any]      = mapped_column(PGJSON, default=lambda: dict(_DEFAULT_FEATURES))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TenantUsage(Base):
    __tablename__  = "tenant_usage"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period", name="uq_tenant_usage_period"),
        Index("idx_tenant_usage_tenant", "tenant_id"),
    )

    id:        Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period:    Mapped[str] = mapped_column(String(7),  nullable=False)   # YYYY-MM

    queries_count:    Mapped[int] = mapped_column(Integer, default=0)
    llm_tokens_used:  Mapped[int] = mapped_column(Integer, default=0)
    storage_used_mb:  Mapped[int] = mapped_column(Integer, default=0)
    documents_count:  Mapped[int] = mapped_column(Integer, default=0)
    users_count:      Mapped[int] = mapped_column(Integer, default=0)

    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ──────────────────────────── G5.1 套餐 ────────────────────────────

class Plan(Base):
    __tablename__ = "plans"

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name:         Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), default="")

    max_users:               Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_documents:           Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_storage_mb:          Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_queries_per_month:   Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_llm_tokens_per_month:Mapped[int | None] = mapped_column(Integer, nullable=True)

    features: Mapped[Any] = mapped_column(PGJSON, default=dict)

    monthly_price_cny: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    yearly_price_cny:  Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ──────────────────────────── G5.2 订阅 ────────────────────────────

class Subscription(Base):
    __tablename__  = "subscriptions"
    __table_args__ = (Index("idx_subscription_tenant", "tenant_id"),)

    id:        Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_id:   Mapped[str] = mapped_column(String(36), nullable=False)

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date:   Mapped[date | None] = mapped_column(Date, nullable=True)

    status:      Mapped[str]  = mapped_column(String(20), default="active")   # active/expired/cancelled
    auto_renew:  Mapped[bool] = mapped_column(Boolean, default=False)
    period:      Mapped[str]  = mapped_column(String(10), default="monthly")  # monthly/yearly
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ──────────────────────────── G5.3 账单 ────────────────────────────

class Bill(Base):
    __tablename__  = "bills"
    __table_args__ = (Index("idx_bill_tenant_period", "tenant_id", "billing_period"),)

    id:             Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id:      Mapped[str] = mapped_column(String(36), nullable=False)
    billing_period: Mapped[str] = mapped_column(String(7),  nullable=False)   # YYYY-MM

    base_amount:    Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    overage_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    discount:       Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total_amount:   Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    status:  Mapped[str]      = mapped_column(String(20), default="pending")  # pending/paid/overdue
    details: Mapped[Any]      = mapped_column(PGJSON, default=dict)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime]     = mapped_column(DateTime, server_default=func.now())
