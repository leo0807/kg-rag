from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable, TypeVar

from .providers import AnthropicProvider, OpenAICompatProvider

logger = logging.getLogger(__name__)
T = TypeVar("T")


def run_sync_with_timeout(
    func: Callable[..., T],
    timeout: float,
    *args: Any,
    timeout_message: str = "LLM响应超时，请重试",
    **kwargs: Any,
) -> T:
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        logger.error("LLM调用超时（%.0fs）", timeout)
        future.cancel()
        raise TimeoutError(timeout_message) from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


async def run_async_with_timeout(awaitable, timeout: float, timeout_message: str = "LLM响应超时，请重试"):
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError as exc:
        logger.error("LLM调用超时（%.0fs）", timeout)
        raise TimeoutError(timeout_message) from exc


def chat_with_timeout(provider, messages: list[dict], timeout: float, **kwargs) -> str:
    return run_sync_with_timeout(provider.chat, timeout, messages, **kwargs)


def chat_with_usage_with_timeout(provider, messages: list[dict], timeout: float, **kwargs) -> tuple[str, dict]:
    return run_sync_with_timeout(provider.chat_with_usage, timeout, messages, **kwargs)


async def stream_chat_with_timeout(provider, messages: list[dict], timeout: float, **kwargs):
    try:
        async with asyncio.timeout(timeout):
            async for chunk in provider.stream_chat(messages, timeout=timeout, **kwargs):
                yield chunk
    except TimeoutError as exc:
        logger.error("LLM流式调用超时（%.0fs）", timeout)
        raise exc


async def chat_with_tools_with_timeout(provider, messages: list[dict], tools: list[dict], timeout: float, **kwargs) -> dict:
    if isinstance(provider, OpenAICompatProvider):
        from .service import LLMService

        service = LLMService.__new__(LLMService)
        service._provider = provider
        service._settings = type("_S", (), {"LLM_TIMEOUT": timeout})()
        return await service._chat_with_tools_openai_compat(messages, tools, timeout=timeout, **kwargs)
    if isinstance(provider, AnthropicProvider):
        from .service import LLMService

        service = LLMService.__new__(LLMService)
        service._provider = provider
        service._settings = type("_S", (), {"LLM_TIMEOUT": timeout})()
        return await service._chat_with_tools_anthropic(messages, tools, timeout=timeout, **kwargs)
    text = chat_with_timeout(provider, messages, timeout, **kwargs)
    return {"text": text}
