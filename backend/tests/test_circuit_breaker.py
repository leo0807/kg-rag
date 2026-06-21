"""Unit tests for LLM circuit breaker state machine."""
import time
from unittest.mock import patch

from src.services.ai.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    reset_circuit_breaker,
    get_circuit_breaker,
)


def _make(failure_threshold: int = 3, reset_timeout: float = 30.0) -> CircuitBreaker:
    return CircuitBreaker(
        CircuitBreakerConfig(failure_threshold=failure_threshold, reset_timeout_seconds=reset_timeout)
    )


class TestClosedState:
    def test_initial_state_is_closed(self):
        cb = _make()
        assert cb.state == CircuitState.CLOSED

    def test_call_allowed_when_closed(self):
        cb = _make()
        assert cb.call_allowed() is True

    def test_single_failure_stays_closed(self):
        cb = _make(failure_threshold=3)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_consecutive_failures_below_threshold_stay_closed(self):
        cb = _make(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        cb = _make(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # need two more to trip; one more should not trip
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED


class TestOpenState:
    def test_threshold_failures_open_circuit(self):
        cb = _make(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_call_not_allowed_when_open(self):
        cb = _make(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.call_allowed() is False

    def test_transitions_to_half_open_after_timeout(self):
        cb = _make(failure_threshold=1, reset_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.05)
        allowed = cb.call_allowed()
        assert allowed is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_call_not_allowed_before_timeout_expires(self):
        cb = _make(failure_threshold=1, reset_timeout=999.0)
        cb.record_failure()
        assert cb.call_allowed() is False


class TestHalfOpenState:
    def _trip_and_wait(self, cb: CircuitBreaker) -> None:
        cb.record_failure()
        time.sleep(0.05)
        cb.call_allowed()  # triggers OPEN → HALF_OPEN transition

    def test_probe_success_closes_circuit(self):
        cb = _make(failure_threshold=1, reset_timeout=0.01)
        self._trip_and_wait(cb)
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_probe_failure_reopens_circuit(self):
        cb = _make(failure_threshold=1, reset_timeout=0.01)
        self._trip_and_wait(cb)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_max_half_open_calls_enforced(self):
        # With half_open_max_calls=1, the HALF_OPEN probe counter starts at 0 after
        # the OPEN→HALF_OPEN transition; the transition itself does NOT consume the
        # counter. So calls: transition(True) + first_probe(True) + second_probe(False).
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, reset_timeout_seconds=0.01, half_open_max_calls=1)
        )
        self._trip_and_wait(cb)     # uses the transition True (counter stays 0)
        cb.call_allowed()            # first HALF_OPEN probe (counter → 1, returns True)
        assert cb.call_allowed() is False   # probe exhausted (1 < 1 is False)


class TestGlobalBreaker:
    def test_reset_creates_fresh_breaker(self):
        # settings is imported lazily inside get_circuit_breaker(), so we patch at source
        reset_circuit_breaker()
        with patch("src.core.config.settings") as mock_settings:
            mock_settings.LLM_CIRCUIT_BREAKER_THRESHOLD = 5
            mock_settings.LLM_CIRCUIT_BREAKER_RESET_SECONDS = 30.0
            cb1 = get_circuit_breaker()
            cb1.record_failure()
            reset_circuit_breaker()
            cb2 = get_circuit_breaker()
        assert cb1 is not cb2
        assert cb2.state == CircuitState.CLOSED
