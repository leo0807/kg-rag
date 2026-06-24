"""
Unit tests for src/services/infra/cache.py
Tests make_cache_key logic without a live Redis connection.
get_cached_result / set_cached_result are tested with a mocked Redis client.
"""
import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

# Patch Redis before importing to avoid real connection
_fake_redis = MagicMock()
_fake_redis.get.return_value = None
_fake_redis.setex.return_value = True


@pytest.fixture(autouse=True)
def patch_redis():
    """Replace get_redis() and settings across all tests in this module."""
    with patch("src.services.infra.cache.get_redis", return_value=_fake_redis), \
         patch("src.services.infra.cache.settings") as mock_settings:
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_settings.QUERY_CACHE_TTL = 300
        _fake_redis.reset_mock()
        _fake_redis.get.return_value = None
        yield mock_settings


from src.services.infra.cache import (
    make_cache_key,
    get_cached_result,
    set_cached_result,
    QUERY_CACHE_VERSION,
)


# ── make_cache_key ────────────────────────────────────────────────────────────

def test_make_cache_key_returns_string():
    key = make_cache_key("what is X?", "hybrid", 5)
    assert isinstance(key, str)


def test_make_cache_key_starts_with_prefix():
    key = make_cache_key("q", "strategy", 3)
    assert key.startswith("query:")


def test_make_cache_key_is_md5_hex():
    key = make_cache_key("q", "strategy", 3)
    hex_part = key[len("query:"):]
    assert len(hex_part) == 32
    int(hex_part, 16)  # must be valid hex


def test_make_cache_key_deterministic():
    k1 = make_cache_key("hello", "dense", 10)
    k2 = make_cache_key("hello", "dense", 10)
    assert k1 == k2


def test_make_cache_key_differs_by_question():
    k1 = make_cache_key("question A", "dense", 5)
    k2 = make_cache_key("question B", "dense", 5)
    assert k1 != k2


def test_make_cache_key_differs_by_strategy():
    k1 = make_cache_key("same", "dense", 5)
    k2 = make_cache_key("same", "sparse", 5)
    assert k1 != k2


def test_make_cache_key_differs_by_top_k():
    k1 = make_cache_key("same", "hybrid", 5)
    k2 = make_cache_key("same", "hybrid", 10)
    assert k1 != k2


def test_make_cache_key_includes_version():
    # Verify the key is built from the versioned raw string
    raw = f"{QUERY_CACHE_VERSION}:my question:hybrid:5"
    expected_hex = hashlib.md5(raw.encode()).hexdigest()
    key = make_cache_key("my question", "hybrid", 5)
    assert key == f"query:{expected_hex}"


# ── get_cached_result ─────────────────────────────────────────────────────────

def test_get_cached_result_miss():
    _fake_redis.get.return_value = None
    result = get_cached_result("question", "hybrid", 5)
    assert result is None


def test_get_cached_result_hit():
    payload = {"answer": "42", "sources": []}
    _fake_redis.get.return_value = json.dumps(payload)
    result = get_cached_result("question", "hybrid", 5)
    assert result == payload


def test_get_cached_result_redis_error_returns_none():
    _fake_redis.get.side_effect = Exception("connection refused")
    result = get_cached_result("question", "hybrid", 5)
    assert result is None
    _fake_redis.get.side_effect = None  # reset


# ── set_cached_result ─────────────────────────────────────────────────────────

def test_set_cached_result_calls_setex():
    payload = {"answer": "hello"}
    set_cached_result("q", "hybrid", 5, payload)
    assert _fake_redis.setex.called


def test_set_cached_result_uses_correct_ttl(patch_redis):
    patch_redis.QUERY_CACHE_TTL = 600
    payload = {"answer": "data"}
    set_cached_result("q2", "dense", 3, payload)
    call_args = _fake_redis.setex.call_args
    # setex(key, ttl, value)
    ttl_arg = call_args[0][1]
    assert ttl_arg == 600


def test_set_cached_result_redis_error_does_not_raise():
    _fake_redis.setex.side_effect = Exception("write failed")
    # Should NOT raise; cache failures are swallowed
    set_cached_result("q", "hybrid", 5, {"answer": "ok"})
    _fake_redis.setex.side_effect = None  # reset
