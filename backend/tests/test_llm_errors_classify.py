"""Unit tests for LLM error classification helpers."""
import pytest
from src.services.ai.errors import (
    LLMError,
    classify_llm_error,
    parse_response_for_business_error,
    map_exception,
    trim_preview,
    RETRIABLE_CODES,
)


class TestLLMError:
    def test_message_is_exception_message(self):
        err = LLMError("rate_limited", "超频")
        assert str(err) == "超频"

    def test_fields_stored(self):
        err = LLMError("timeout", "超时", status_code=504, endpoint="/v1/chat", retriable=True)
        assert err.code == "timeout"
        assert err.status_code == 504
        assert err.endpoint == "/v1/chat"
        assert err.retriable is True

    def test_default_retriable_is_false(self):
        err = LLMError("auth_failed", "鉴权失败")
        assert err.retriable is False


class TestRetrialCodes:
    def test_rate_limited_is_retriable(self):
        assert "rate_limited" in RETRIABLE_CODES

    def test_timeout_is_retriable(self):
        assert "timeout" in RETRIABLE_CODES

    def test_auth_failed_not_retriable(self):
        assert "auth_failed" not in RETRIABLE_CODES


class TestClassifyLlmError:
    def test_401_auth_failed(self):
        err = classify_llm_error(401)
        assert err.code == "auth_failed"
        assert err.status_code == 401

    def test_429_rate_limited_and_retriable(self):
        err = classify_llm_error(429)
        assert err.code == "rate_limited"
        assert err.retriable is True

    def test_408_timeout_and_retriable(self):
        err = classify_llm_error(408)
        assert err.code == "timeout"
        assert err.retriable is True

    def test_504_timeout(self):
        err = classify_llm_error(504)
        assert err.code == "timeout"

    def test_403_quota_exceeded(self):
        err = classify_llm_error(403, response_text="余额不足 balance insufficient")
        assert err.code == "quota_exceeded"

    def test_403_model_disabled(self):
        err = classify_llm_error(403, response_text="model disabled")
        assert err.code == "model_unavailable"

    def test_403_generic_forbidden(self):
        err = classify_llm_error(403, response_text="access denied")
        assert err.code == "forbidden"

    def test_500_unknown_error(self):
        err = classify_llm_error(500)
        assert err.code == "unknown_error"
        assert err.retriable is True


class TestParseResponseForBusinessError:
    def test_normal_choices_response_returns_none(self):
        assert parse_response_for_business_error({"choices": [{"message": {}}]}) is None

    def test_code_zero_returns_none(self):
        assert parse_response_for_business_error({"code": 0, "message": "ok"}) is None

    def test_code_string_zero_returns_none(self):
        assert parse_response_for_business_error({"code": "0", "message": "ok"}) is None

    def test_non_zero_code_returns_error(self):
        err = parse_response_for_business_error({"code": 1001, "message": "模型不可用"})
        assert err is not None
        assert err.code == "api_invalid_request"
        assert err.provider_code == 1001

    def test_non_dict_returns_none(self):
        assert parse_response_for_business_error("raw string") is None  # type: ignore[arg-type]


class TestMapException:
    def test_llm_error_passed_through(self):
        original = LLMError("timeout", "超时", retriable=True)
        mapped = map_exception(original)
        assert mapped is original

    def test_generic_exception_becomes_unknown_error(self):
        err = map_exception(RuntimeError("something broke"))
        assert err.code == "unknown_error"

    def test_endpoint_preserved(self):
        err = map_exception(RuntimeError("x"), endpoint="/v1/chat")
        assert err.endpoint == "/v1/chat"


class TestTrimPreview:
    def test_short_text_unchanged(self):
        text = "short"
        assert trim_preview(text, limit=100) == text

    def test_long_text_truncated(self):
        text = "x" * 500
        result = trim_preview(text, limit=100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_exact_limit_unchanged(self):
        text = "x" * 400
        assert trim_preview(text) == text

    def test_empty_string(self):
        assert trim_preview("") == ""

    def test_none_like_empty(self):
        assert trim_preview(None) == ""  # type: ignore[arg-type]
