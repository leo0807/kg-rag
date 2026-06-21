"""
tests/test_password.py
密码哈希与校验单元测试
"""
import pytest
pytest.importorskip("passlib", reason="passlib not installed in this environment")
from src.auth.password import hash_password, verify_password


class TestHashPassword:
    def test_returns_string(self):
        assert isinstance(hash_password("secret"), str)

    def test_hash_not_equal_plain(self):
        assert hash_password("secret") != "secret"

    def test_hash_starts_with_bcrypt_marker(self):
        h = hash_password("secret")
        assert h.startswith("$2b$") or h.startswith("$2a$")

    def test_same_password_produces_different_hashes(self):
        # bcrypt uses random salt
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_long_password_truncated_to_72_bytes(self):
        # passwords exceeding 72 bytes should still hash without error
        long_pw = "a" * 100
        h = hash_password(long_pw)
        assert h is not None
        # And it verifies the same as the 72-byte version
        assert verify_password(long_pw, h) is True


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_wrong_password_returns_false(self):
        h = hash_password("mypassword")
        assert verify_password("wrongpassword", h) is False

    def test_empty_password_vs_non_empty_hash(self):
        h = hash_password("something")
        assert verify_password("", h) is False

    def test_empty_password_vs_empty_hash(self):
        h = hash_password("")
        assert verify_password("", h) is True

    def test_case_sensitive(self):
        h = hash_password("Password")
        assert verify_password("password", h) is False
        assert verify_password("PASSWORD", h) is False

    def test_unicode_password(self):
        pw = "密码abc123"
        h = hash_password(pw)
        assert verify_password(pw, h) is True
        assert verify_password("wrong", h) is False

    def test_truncation_consistency(self):
        # 73-char and 72-char passwords should be equivalent after truncation
        base = "x" * 72
        h = hash_password(base)
        assert verify_password(base + "z", h) is True  # 73-char → truncated to 72
