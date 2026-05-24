"""
tests/test_llm_retry.py
LLM 重试 + 熔断器单元测试
"""
import time
import pytest
from unittest.mock import patch

from src.services.ai.errors import LLMError, RETRIABLE_CODES, _is_retriable
from src.services.ai.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from src.services.ai.retry import call_with_retry, _should_retry


def make_breaker(threshold: int = 3, reset_timeout: float = 0.05) -> CircuitBreaker:
    return CircuitBreaker(CircuitBreakerConfig(
        failure_threshold=threshold,
        reset_timeout_seconds=reset_timeout,
        half_open_max_calls=1,
    ))


# ─── errors.py retriable 属性 ────────────────────────────────────────────────

class TestRetriableAttribute:
    def test_retriable_codes_are_retriable(self):
        for code in RETRIABLE_CODES:
            assert _is_retriable(code), f"Expected {code} to be retriable"

    def test_non_retriable_codes_are_not_retriable(self):
        for code in ("auth_failed", "model_unavailable", "quota_exceeded", "forbidden", "api_invalid_request"):
            assert not _is_retriable(code), f"Expected {code} to NOT be retriable"

    def test_llmerror_retriable_field_set_correctly(self):
        e = LLMError("timeout", "msg", retriable=True)
        assert e.retriable is True
        e2 = LLMError("auth_failed", "msg", retriable=False)
        assert e2.retriable is False

    def test_should_retry_true_for_retriable_llmerror(self):
        exc = LLMError("rate_limited", "r", retriable=True)
        assert _should_retry(exc) is True

    def test_should_retry_false_for_non_retriable_llmerror(self):
        exc = LLMError("auth_failed", "a", retriable=False)
        assert _should_retry(exc) is False

    def test_should_retry_false_for_non_llmerror(self):
        assert _should_retry(ValueError("x")) is False


# ─── retry 行为 ──────────────────────────────────────────────────────────────

class TestRetryBehavior:
    def test_retriable_error_retries_until_success(self):
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise LLMError("timeout", "t", retriable=True)
            return "ok"

        breaker = make_breaker(threshold=5)
        with patch("src.services.ai.retry.get_circuit_breaker", return_value=breaker):
            result = call_with_retry(flaky)
        assert result == "ok"
        assert len(attempts) == 3

    def test_non_retriable_error_fails_immediately(self):
        attempts = []

        def fails():
            attempts.append(1)
            raise LLMError("auth_failed", "a", retriable=False)

        breaker = make_breaker(threshold=5)
        with patch("src.services.ai.retry.get_circuit_breaker", return_value=breaker):
            with pytest.raises(LLMError) as exc_info:
                call_with_retry(fails)
        assert exc_info.value.code == "auth_failed"
        assert len(attempts) == 1  # 只尝试一次

    def test_retry_exhausted_raises_last_error(self):
        def always_timeout():
            raise LLMError("timeout", "to", retriable=True)

        breaker = make_breaker(threshold=10)
        with patch("src.services.ai.retry.get_circuit_breaker", return_value=breaker):
            with patch("src.services.ai.retry.settings") as mock_cfg:
                mock_cfg.LLM_RETRY_MAX_ATTEMPTS = 2
                mock_cfg.LLM_RETRY_INITIAL_BACKOFF_SECONDS = 0.001
                with pytest.raises(LLMError) as exc_info:
                    call_with_retry(always_timeout)
        assert exc_info.value.code == "timeout"

    def test_circuit_open_raises_circuit_open_error(self):
        breaker = make_breaker(threshold=1)
        breaker.record_failure()  # trip the breaker immediately
        assert breaker.state == CircuitState.OPEN

        with patch("src.services.ai.retry.get_circuit_breaker", return_value=breaker):
            with pytest.raises(LLMError) as exc_info:
                call_with_retry(lambda: "never called")
        assert exc_info.value.code == "circuit_open"
        assert exc_info.value.retriable is False


# ─── 熔断器状态机 ─────────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_closed_initial_state(self):
        breaker = make_breaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.call_allowed() is True

    def test_closed_to_open_on_threshold(self):
        breaker = make_breaker(threshold=3)
        for _ in range(3):
            assert breaker.call_allowed()
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.call_allowed() is False

    def test_open_to_half_open_after_timeout(self):
        breaker = make_breaker(threshold=1, reset_timeout=0.05)
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        time.sleep(0.1)
        assert breaker.call_allowed() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_to_closed(self):
        breaker = make_breaker(threshold=1, reset_timeout=0.05)
        breaker.record_failure()
        time.sleep(0.1)
        breaker.call_allowed()  # → HALF_OPEN
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_to_open(self):
        breaker = make_breaker(threshold=1, reset_timeout=0.05)
        breaker.record_failure()
        time.sleep(0.1)
        breaker.call_allowed()  # → HALF_OPEN
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_success_resets_consecutive_failures(self):
        breaker = make_breaker(threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()  # 重置计数
        assert breaker.state == CircuitState.CLOSED
        # 再失败 1 次不触发熔断
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
