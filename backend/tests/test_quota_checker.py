"""
tests/test_quota_checker.py
QuotaChecker 单元测试 — 全量 mock DB，不依赖真实数据库
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.multitenant.quota_checker import (
    QuotaChecker,
    QuotaExceededError,
    FeatureNotEnabledError,
    _current_period,
    get_tenant_usage_summary,
    DEFAULT_QUOTA,
)
from src.db.tenant_models import TenantQuota, TenantUsage


# ── helpers ──────────────────────────────────────────────────────────────────

def make_quota(**overrides) -> TenantQuota:
    q = TenantQuota()
    q.tenant_id = "t-test"
    q.max_queries_per_month    = overrides.get("max_queries_per_month",    10_000)
    q.max_llm_tokens_per_month = overrides.get("max_llm_tokens_per_month", 5_000_000)
    q.max_evals_per_month      = overrides.get("max_evals_per_month",      50)
    q.max_users                = overrides.get("max_users",                10)
    q.max_documents            = overrides.get("max_documents",            100)
    q.max_storage_mb           = overrides.get("max_storage_mb",           5_000)
    q.features                 = overrides.get("features",                 {})
    return q


def make_usage(**overrides) -> TenantUsage:
    u = TenantUsage()
    u.tenant_id         = "t-test"
    u.period            = _current_period()
    u.queries_count     = overrides.get("queries_count",     0)
    u.llm_tokens_used   = overrides.get("llm_tokens_used",   0)
    u.storage_used_mb   = overrides.get("storage_used_mb",   0)
    u.users_count       = overrides.get("users_count",       0)
    u.documents_count   = overrides.get("documents_count",   0)
    return u


def make_checker(quota: TenantQuota | None, usage: TenantUsage) -> QuotaChecker:
    db = AsyncMock()
    checker = QuotaChecker(db=db, tenant_id="t-test")
    checker._quota = AsyncMock(return_value=quota)
    checker._usage = AsyncMock(return_value=usage)
    return checker


# ── _current_period ───────────────────────────────────────────────────────────

class TestCurrentPeriod:
    def test_format_yyyy_mm(self):
        period = _current_period()
        import re
        assert re.match(r"^\d{4}-\d{2}$", period)


# ── check_query_quota ─────────────────────────────────────────────────────────

class TestCheckQueryQuota:
    @pytest.mark.asyncio
    async def test_no_quota_passes(self):
        checker = make_checker(None, make_usage())
        assert await checker.check_query_quota() is True

    @pytest.mark.asyncio
    async def test_under_limit_passes(self):
        quota = make_quota(max_queries_per_month=100)
        usage = make_usage(queries_count=50)
        checker = make_checker(quota, usage)
        assert await checker.check_query_quota() is True

    @pytest.mark.asyncio
    async def test_at_limit_raises(self):
        quota = make_quota(max_queries_per_month=100)
        usage = make_usage(queries_count=100)
        checker = make_checker(quota, usage)
        with pytest.raises(QuotaExceededError) as exc:
            await checker.check_query_quota()
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_over_limit_raises(self):
        quota = make_quota(max_queries_per_month=100)
        usage = make_usage(queries_count=150)
        checker = make_checker(quota, usage)
        with pytest.raises(QuotaExceededError):
            await checker.check_query_quota()

    @pytest.mark.asyncio
    async def test_error_message_contains_limit(self):
        quota = make_quota(max_queries_per_month=500)
        usage = make_usage(queries_count=500)
        checker = make_checker(quota, usage)
        with pytest.raises(QuotaExceededError) as exc:
            await checker.check_query_quota()
        assert "500" in exc.value.detail


# ── check_token_quota ─────────────────────────────────────────────────────────

class TestCheckTokenQuota:
    @pytest.mark.asyncio
    async def test_no_quota_passes(self):
        checker = make_checker(None, make_usage())
        assert await checker.check_token_quota(1000) is True

    @pytest.mark.asyncio
    async def test_tokens_within_limit_passes(self):
        quota = make_quota(max_llm_tokens_per_month=10_000)
        usage = make_usage(llm_tokens_used=5_000)
        checker = make_checker(quota, usage)
        assert await checker.check_token_quota(4_000) is True

    @pytest.mark.asyncio
    async def test_tokens_exceeding_limit_raises(self):
        quota = make_quota(max_llm_tokens_per_month=10_000)
        usage = make_usage(llm_tokens_used=9_500)
        checker = make_checker(quota, usage)
        with pytest.raises(QuotaExceededError):
            await checker.check_token_quota(600)

    @pytest.mark.asyncio
    async def test_zero_tokens_at_limit_raises(self):
        quota = make_quota(max_llm_tokens_per_month=1_000)
        usage = make_usage(llm_tokens_used=1_000)
        checker = make_checker(quota, usage)
        with pytest.raises(QuotaExceededError):
            await checker.check_token_quota(0)


# ── check_storage_quota ───────────────────────────────────────────────────────

class TestCheckStorageQuota:
    @pytest.mark.asyncio
    async def test_no_quota_passes(self):
        checker = make_checker(None, make_usage())
        assert await checker.check_storage_quota(999) is True

    @pytest.mark.asyncio
    async def test_within_limit_passes(self):
        quota = make_quota(max_storage_mb=1_000)
        usage = make_usage(storage_used_mb=500)
        checker = make_checker(quota, usage)
        assert await checker.check_storage_quota(400) is True

    @pytest.mark.asyncio
    async def test_over_limit_raises(self):
        quota = make_quota(max_storage_mb=1_000)
        usage = make_usage(storage_used_mb=900)
        checker = make_checker(quota, usage)
        with pytest.raises(QuotaExceededError):
            await checker.check_storage_quota(200)


# ── check_user_quota ──────────────────────────────────────────────────────────

class TestCheckUserQuota:
    @pytest.mark.asyncio
    async def test_no_quota_passes(self):
        checker = make_checker(None, make_usage())
        assert await checker.check_user_quota(999) is True

    @pytest.mark.asyncio
    async def test_under_limit_passes(self):
        quota = make_quota(max_users=10)
        usage = make_usage()
        checker = make_checker(quota, usage)
        assert await checker.check_user_quota(9) is True

    @pytest.mark.asyncio
    async def test_at_limit_raises(self):
        quota = make_quota(max_users=10)
        usage = make_usage()
        checker = make_checker(quota, usage)
        with pytest.raises(QuotaExceededError):
            await checker.check_user_quota(10)


# ── check_feature ─────────────────────────────────────────────────────────────

class TestCheckFeature:
    @pytest.mark.asyncio
    async def test_no_quota_passes(self):
        checker = make_checker(None, make_usage())
        assert await checker.check_feature("advanced_search") is True

    @pytest.mark.asyncio
    async def test_feature_enabled_passes(self):
        quota = make_quota(features={"advanced_search": True})
        checker = make_checker(quota, make_usage())
        assert await checker.check_feature("advanced_search") is True

    @pytest.mark.asyncio
    async def test_feature_disabled_raises(self):
        quota = make_quota(features={"advanced_search": False})
        checker = make_checker(quota, make_usage())
        with pytest.raises(FeatureNotEnabledError) as exc:
            await checker.check_feature("advanced_search")
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_unknown_feature_defaults_to_enabled(self):
        # features not listed → defaults to True (permissive)
        quota = make_quota(features={})
        checker = make_checker(quota, make_usage())
        assert await checker.check_feature("unknown_feature") is True

    @pytest.mark.asyncio
    async def test_error_message_contains_feature_name(self):
        quota = make_quota(features={"export_pdf": False})
        checker = make_checker(quota, make_usage())
        with pytest.raises(FeatureNotEnabledError) as exc:
            await checker.check_feature("export_pdf")
        assert "export_pdf" in exc.value.detail


# ── QuotaExceededError / FeatureNotEnabledError status codes ─────────────────

class TestErrorClasses:
    def test_quota_exceeded_is_429(self):
        err = QuotaExceededError("超出限制")
        assert err.status_code == 429
        assert err.detail == "超出限制"

    def test_feature_not_enabled_is_403(self):
        err = FeatureNotEnabledError("功能未开通")
        assert err.status_code == 403
        assert err.detail == "功能未开通"
