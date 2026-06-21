"""
tests/test_jwt.py
JWT 生成与解码单元测试
"""
import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from jose import jwt as jose_jwt

from src.auth.jwt import create_access_token, decode_token, ALGORITHM
from src.core.config import settings


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token("user-1", is_admin=False)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_payload_sub(self):
        token = create_access_token("user-42", is_admin=False)
        payload = decode_token(token)
        assert payload["sub"] == "user-42"

    def test_payload_is_admin_false(self):
        token = create_access_token("user-1", is_admin=False)
        payload = decode_token(token)
        assert payload["is_admin"] is False

    def test_payload_is_admin_true(self):
        token = create_access_token("admin-1", is_admin=True)
        payload = decode_token(token)
        assert payload["is_admin"] is True

    def test_payload_tenant_id_included(self):
        token = create_access_token("user-1", is_admin=False, tenant_id="t-123")
        payload = decode_token(token)
        assert payload["tenant_id"] == "t-123"

    def test_payload_no_tenant_id_when_none(self):
        token = create_access_token("user-1", is_admin=False, tenant_id=None)
        payload = decode_token(token)
        assert "tenant_id" not in payload

    def test_has_exp_field(self):
        token = create_access_token("user-1", is_admin=False)
        payload = decode_token(token)
        assert "exp" in payload

    def test_exp_in_future(self):
        token = create_access_token("user-1", is_admin=False)
        payload = decode_token(token)
        assert payload["exp"] > time.time()

    def test_different_users_produce_different_tokens(self):
        t1 = create_access_token("user-1", is_admin=False)
        t2 = create_access_token("user-2", is_admin=False)
        assert t1 != t2

    def test_algorithm_is_hs256(self):
        token = create_access_token("user-1", is_admin=False)
        header = jose_jwt.get_unverified_header(token)
        assert header["alg"] == ALGORITHM


class TestDecodeToken:
    def test_valid_token_returns_payload(self):
        token = create_access_token("user-99", is_admin=True, tenant_id="t-1")
        payload = decode_token(token)
        assert payload["sub"] == "user-99"
        assert payload["is_admin"] is True
        assert payload["tenant_id"] == "t-1"

    def test_invalid_token_raises_value_error(self):
        with pytest.raises(ValueError, match="无效的 token"):
            decode_token("not.a.valid.token")

    def test_tampered_token_raises_value_error(self):
        token = create_access_token("user-1", is_admin=False)
        tampered = token[:-4] + "XXXX"
        with pytest.raises(ValueError):
            decode_token(tampered)

    def test_wrong_secret_raises_value_error(self):
        token = jose_jwt.encode(
            {"sub": "user-1", "is_admin": False, "exp": datetime.utcnow() + timedelta(hours=1)},
            "wrong-secret",
            algorithm=ALGORITHM,
        )
        with pytest.raises(ValueError):
            decode_token(token)

    def test_expired_token_raises_value_error(self):
        expired_token = jose_jwt.encode(
            {"sub": "user-1", "is_admin": False, "exp": datetime.utcnow() - timedelta(seconds=1)},
            settings.JWT_SECRET,
            algorithm=ALGORITHM,
        )
        with pytest.raises(ValueError):
            decode_token(expired_token)

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            decode_token("")
