"""
tests/test_tenant_filter.py
多租户工具函数单元测试
"""
import pytest
from unittest.mock import MagicMock

from src.services.multitenant.tenant_filter import (
    TenantQueryMixin,
    get_tenant_id,
    get_tenant_id_optional,
    build_milvus_tenant_expr,
    inject_neo4j_tenant,
)


# ── get_tenant_id ─────────────────────────────────────────────────────────────

class TestGetTenantId:
    def _make_request(self, tenant_id=None):
        req = MagicMock()
        req.state = MagicMock(spec=[])
        if tenant_id is not None:
            req.state.tenant_id = tenant_id
        return req

    def test_returns_tenant_id_when_present(self):
        from fastapi import HTTPException
        req = self._make_request("t-abc")
        assert get_tenant_id(req) == "t-abc"

    def test_raises_403_when_missing(self):
        from fastapi import HTTPException
        req = self._make_request(None)
        with pytest.raises(HTTPException) as exc:
            get_tenant_id(req)
        assert exc.value.status_code == 403

    def test_raises_403_when_empty_string(self):
        from fastapi import HTTPException
        req = self._make_request("")
        with pytest.raises(HTTPException) as exc:
            get_tenant_id(req)
        assert exc.value.status_code == 403


# ── get_tenant_id_optional ────────────────────────────────────────────────────

class TestGetTenantIdOptional:
    def _make_request(self, tenant_id=None, has_attr=True):
        req = MagicMock()
        if has_attr:
            req.state = MagicMock(spec=["tenant_id"])
            req.state.tenant_id = tenant_id
        else:
            req.state = MagicMock(spec=[])
        return req

    def test_returns_tenant_id_when_present(self):
        req = self._make_request("t-xyz")
        assert get_tenant_id_optional(req) == "t-xyz"

    def test_returns_none_when_not_set(self):
        req = MagicMock()
        req.state = MagicMock(spec=[])  # no tenant_id attribute
        assert get_tenant_id_optional(req) is None

    def test_returns_none_when_none(self):
        req = self._make_request(None)
        assert get_tenant_id_optional(req) is None


# ── build_milvus_tenant_expr ──────────────────────────────────────────────────

class TestBuildMilvusTenantExpr:
    def test_without_original_expr(self):
        expr = build_milvus_tenant_expr("t-1")
        assert expr == 'tenant_id == "t-1"'

    def test_with_original_expr(self):
        expr = build_milvus_tenant_expr("t-1", 'doc_type == "spec"')
        assert "t-1" in expr
        assert 'doc_type == "spec"' in expr
        assert " and " in expr

    def test_empty_original_expr_treated_as_no_expr(self):
        expr_empty = build_milvus_tenant_expr("t-1", "")
        expr_none  = build_milvus_tenant_expr("t-1")
        assert expr_empty == expr_none

    def test_tenant_id_quoted(self):
        expr = build_milvus_tenant_expr("tenant-with-dashes")
        assert '"tenant-with-dashes"' in expr

    def test_combined_expr_wrapped_in_parens(self):
        expr = build_milvus_tenant_expr("t-1", "x == 1")
        assert expr.startswith("(x == 1)")


# ── inject_neo4j_tenant ───────────────────────────────────────────────────────

class TestInjectNeo4jTenant:
    def test_injects_tenant_id(self):
        result = inject_neo4j_tenant({"name": "val"}, "t-neo4j")
        assert result["tenant_id"] == "t-neo4j"

    def test_preserves_original_params(self):
        result = inject_neo4j_tenant({"a": 1, "b": 2}, "t-1")
        assert result["a"] == 1
        assert result["b"] == 2

    def test_does_not_mutate_original_dict(self):
        original = {"x": 10}
        result = inject_neo4j_tenant(original, "t-1")
        assert "tenant_id" not in original
        assert "tenant_id" in result

    def test_empty_params(self):
        result = inject_neo4j_tenant({}, "t-empty")
        assert result == {"tenant_id": "t-empty"}

    def test_overwrites_existing_tenant_id(self):
        result = inject_neo4j_tenant({"tenant_id": "old"}, "new-t")
        assert result["tenant_id"] == "new-t"
