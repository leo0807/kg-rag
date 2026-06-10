"""
G4.2 配额检查服务
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.tenant_models import TenantQuota, TenantUsage

logger = logging.getLogger(__name__)

DEFAULT_QUOTA = {
    "max_queries_per_month": 10_000,
    "max_llm_tokens_per_month": 5_000_000,
    "max_evals_per_month": 50,
    "max_users": 10,
    "max_documents": 100,
    "max_storage_mb": 5_000,
}


class QuotaExceededError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=429, detail=detail)


class FeatureNotEnabledError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=403, detail=detail)


def _current_period() -> str:
    return datetime.utcnow().strftime("%Y-%m")


async def _get_quota(db: AsyncSession, tenant_id: str) -> TenantQuota | None:
    return (
        await db.execute(select(TenantQuota).where(TenantQuota.tenant_id == tenant_id))
    ).scalar_one_or_none()


async def _get_or_create_usage(db: AsyncSession, tenant_id: str, period: str) -> TenantUsage:
    usage = (
        await db.execute(
            select(TenantUsage).where(
                TenantUsage.tenant_id == tenant_id, TenantUsage.period == period
            )
        )
    ).scalar_one_or_none()
    if usage is None:
        usage = TenantUsage(tenant_id=tenant_id, period=period)
        db.add(usage)
        await db.flush()
    return usage


class QuotaChecker:
    def __init__(self, db: AsyncSession, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    async def _quota(self) -> TenantQuota | None:
        return await _get_quota(self.db, self.tenant_id)

    async def _usage(self) -> TenantUsage:
        return await _get_or_create_usage(self.db, self.tenant_id, _current_period())

    async def check_query_quota(self) -> bool:
        quota = await self._quota()
        if quota is None:
            return True
        usage = await self._usage()
        limit = quota.max_queries_per_month
        if usage.queries_count >= limit:
            raise QuotaExceededError(f"查询次数已达上限（{limit}/月）")
        return True

    async def check_token_quota(self, tokens: int = 0) -> bool:
        quota = await self._quota()
        if quota is None:
            return True
        usage = await self._usage()
        limit = quota.max_llm_tokens_per_month
        if usage.llm_tokens_used + tokens >= limit:
            raise QuotaExceededError(f"LLM Token 用量已达上限（{limit}/月）")
        return True

    async def check_storage_quota(self, new_size_mb: float) -> bool:
        quota = await self._quota()
        if quota is None:
            return True
        usage = await self._usage()
        if usage.storage_used_mb + new_size_mb > quota.max_storage_mb:
            raise QuotaExceededError(f"存储空间不足（上限 {quota.max_storage_mb} MB）")
        return True

    async def check_user_quota(self, current_count: int) -> bool:
        quota = await self._quota()
        if quota is None:
            return True
        if current_count >= quota.max_users:
            raise QuotaExceededError(f"用户数已达上限（{quota.max_users}）")
        return True

    async def check_feature(self, feature: str) -> bool:
        quota = await self._quota()
        if quota is None:
            return True
        features: dict = quota.features or {}
        if not features.get(feature, True):
            raise FeatureNotEnabledError(f"功能未开通: {feature}")
        return True

    async def record_query(self, tokens: int = 0) -> None:
        usage = await self._usage()
        usage.queries_count += 1
        usage.llm_tokens_used += tokens
        await self.db.commit()

    async def record_storage(self, delta_mb: float) -> None:
        usage = await self._usage()
        usage.storage_used_mb = max(0, usage.storage_used_mb + int(delta_mb))
        await self.db.commit()


async def get_tenant_usage_summary(db: AsyncSession, tenant_id: str) -> dict:
    """返回当月用量 + 配额概览。"""
    period = _current_period()
    usage = await _get_or_create_usage(db, tenant_id, period)
    quota = await _get_quota(db, tenant_id)

    def pct(used: int, limit: int) -> float:
        return round(used / limit * 100, 1) if limit else 0

    q = quota or TenantQuota(tenant_id=tenant_id)
    return {
        "period": period,
        "queries": {"used": usage.queries_count, "limit": q.max_queries_per_month,
                    "pct": pct(usage.queries_count, q.max_queries_per_month)},
        "tokens": {"used": usage.llm_tokens_used, "limit": q.max_llm_tokens_per_month,
                   "pct": pct(usage.llm_tokens_used, q.max_llm_tokens_per_month)},
        "storage_mb": {"used": usage.storage_used_mb, "limit": q.max_storage_mb,
                       "pct": pct(usage.storage_used_mb, q.max_storage_mb)},
        "users": {"used": usage.users_count, "limit": q.max_users,
                  "pct": pct(usage.users_count, q.max_users)},
        "documents": {"used": usage.documents_count, "limit": q.max_documents,
                      "pct": pct(usage.documents_count, q.max_documents)},
        "features": q.features or {},
    }
