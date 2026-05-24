from __future__ import annotations

"""LLM 熔断器（线程安全）。"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock

log = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"        # 正常工作
    OPEN = "open"            # 熔断中，拒绝所有请求
    HALF_OPEN = "half_open"  # 试探恢复


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    reset_timeout_seconds: float = 30.0
    half_open_max_calls: int = 1


class CircuitBreaker:
    """状态机: CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN"""

    def __init__(self, config: CircuitBreakerConfig):
        self._config = config
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._open_since: float | None = None
        self._half_open_attempts = 0
        self._lock = Lock()

    def call_allowed(self) -> bool:
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - (self._open_since or 0)
                if elapsed >= self._config.reset_timeout_seconds:
                    log.info("CircuitBreaker OPEN → HALF_OPEN after %.1fs", elapsed)
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_attempts = 0
                    return True
                return False
            # HALF_OPEN
            if self._half_open_attempts < self._config.half_open_max_calls:
                self._half_open_attempts += 1
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                log.info("CircuitBreaker HALF_OPEN → CLOSED (probe succeeded)")
                self._state = CircuitState.CLOSED
            self._consecutive_failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == CircuitState.HALF_OPEN:
                log.warning("CircuitBreaker HALF_OPEN → OPEN (probe failed, failures=%d)", self._consecutive_failures)
                self._state = CircuitState.OPEN
                self._open_since = time.monotonic()
                return
            if self._state == CircuitState.CLOSED and self._consecutive_failures >= self._config.failure_threshold:
                log.error("CircuitBreaker CLOSED → OPEN (threshold %d reached)", self._config.failure_threshold)
                self._state = CircuitState.OPEN
                self._open_since = time.monotonic()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state


_global_breaker: CircuitBreaker | None = None
_breaker_lock = Lock()


def get_circuit_breaker() -> CircuitBreaker:
    global _global_breaker
    if _global_breaker is None:
        with _breaker_lock:
            if _global_breaker is None:
                from ...core.config import settings
                config = CircuitBreakerConfig(
                    failure_threshold=settings.LLM_CIRCUIT_BREAKER_THRESHOLD,
                    reset_timeout_seconds=settings.LLM_CIRCUIT_BREAKER_RESET_SECONDS,
                )
                _global_breaker = CircuitBreaker(config)
    return _global_breaker


def reset_circuit_breaker() -> None:
    """在配置热重载后调用，让下次 get_circuit_breaker() 用新配置重建。"""
    global _global_breaker
    with _breaker_lock:
        _global_breaker = None
    log.info("CircuitBreaker reset (will rebuild on next call)")
