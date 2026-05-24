from __future__ import annotations

"""LLM 调用重试 + 熔断集成（基于 tenacity）。"""

import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    AsyncRetrying,
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ...core.config import settings
from .circuit_breaker import get_circuit_breaker
from .errors import LLMError

log = logging.getLogger(__name__)

T = TypeVar("T")


def _should_retry(exc: BaseException) -> bool:
    return isinstance(exc, LLMError) and exc.retriable


def _make_circuit_open_error(breaker) -> LLMError:
    return LLMError(
        code="circuit_open",
        message=f"LLM 服务熔断中(state={breaker.state.value})，请稍后重试",
        retriable=False,
    )


def call_with_retry(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """同步 LLM 调用 + 指数退避重试 + 熔断检查。

    - 不可重试的 LLMError (retriable=False) 立即抛出，不重试。
    - 熔断开路时直接抛 LLMError(code="circuit_open")。
    """
    breaker = get_circuit_breaker()
    if not breaker.call_allowed():
        raise _make_circuit_open_error(breaker)

    retrying = Retrying(
        stop=stop_after_attempt(settings.LLM_RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.LLM_RETRY_INITIAL_BACKOFF_SECONDS,
            min=settings.LLM_RETRY_INITIAL_BACKOFF_SECONDS,
            max=30.0,
        ),
        retry=retry_if_exception(_should_retry),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    try:
        result = retrying(func, *args, **kwargs)
        breaker.record_success()
        return result
    except LLMError as exc:
        if exc.retriable:
            breaker.record_failure()
        raise


async def acall_with_retry(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """异步 LLM 调用 + 指数退避重试 + 熔断检查。"""
    breaker = get_circuit_breaker()
    if not breaker.call_allowed():
        raise _make_circuit_open_error(breaker)

    retrying = AsyncRetrying(
        stop=stop_after_attempt(settings.LLM_RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.LLM_RETRY_INITIAL_BACKOFF_SECONDS,
            min=settings.LLM_RETRY_INITIAL_BACKOFF_SECONDS,
            max=30.0,
        ),
        retry=retry_if_exception(_should_retry),
        reraise=True,
    )
    result: Any = None
    try:
        async for attempt in retrying:
            with attempt:
                result = await func(*args, **kwargs)
        breaker.record_success()
        return result
    except LLMError as exc:
        if exc.retriable:
            breaker.record_failure()
        raise
