"""
vLLM client — drop-in replacement for OpenAI-compatible LLM calls.

Targets a locally running `vllm serve` instance (PagedAttention + prefix cache).
Implements the same chat / stream_chat interface as other providers so it can
be selected via LLM_PROVIDER=vllm in environment config.

Start vLLM server:
  vllm serve Qwen2.5-7B-Instruct \
      --port 8001 \
      --enable-prefix-caching \
      --max-model-len 8192 \
      --gpu-memory-utilization 0.90 \
      --trust-remote-code

Prefix caching behaviour (server-side, no client changes needed):
  - vLLM caches KV blocks for identical prompt prefixes across requests.
  - All requests using the same system prompt reuse the cached KV, reducing
    TTFT (time-to-first-token) for repeated prefixes by 60-80%.
  - Works automatically when --enable-prefix-caching is set.
  - Compatible with the Anthropic prompt_cache.py strategy: both reduce
    redundant computation for shared context.
"""
from __future__ import annotations

import json
import logging
import os
from typing import AsyncGenerator, Iterator

log = logging.getLogger(__name__)

VLLM_BASE_URL  = os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1")
VLLM_MODEL     = os.getenv("VLLM_MODEL", "Qwen2.5-7B-Instruct")
VLLM_API_KEY   = os.getenv("VLLM_API_KEY", "EMPTY")   # vLLM accepts any key
VLLM_TIMEOUT   = int(os.getenv("VLLM_TIMEOUT", "60"))
VLLM_MAX_TOKENS = int(os.getenv("VLLM_MAX_TOKENS", "2048"))


class VLLMProvider:
    """Synchronous vLLM provider (wraps httpx for blocking calls)."""

    def __init__(
        self,
        base_url: str = VLLM_BASE_URL,
        model: str = VLLM_MODEL,
        api_key: str = VLLM_API_KEY,
        timeout: int = VLLM_TIMEOUT,
        max_tokens: int = VLLM_MAX_TOKENS,
    ) -> None:
        self._base_url  = base_url.rstrip("/")
        self._model     = model
        self._api_key   = api_key
        self._timeout   = timeout
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        return self._model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages: list[dict], **kwargs) -> dict:
        return {
            "model":      self._model,
            "messages":   messages,
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", 0.1),
            "stream":     False,
        }

    def chat(self, messages: list[dict], **kwargs) -> str:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("pip install httpx")

        payload = self._build_payload(messages, **kwargs)
        with httpx.Client(timeout=self._timeout) as c:
            resp = c.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def stream_chat(self, messages: list[dict], **kwargs) -> Iterator[str]:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("pip install httpx")

        payload = {**self._build_payload(messages, **kwargs), "stream": True}
        with httpx.Client(timeout=self._timeout) as c:
            with c.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0]["delta"]
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError):
                        continue


class AsyncVLLMProvider:
    """Async vLLM provider for FastAPI / asyncio contexts."""

    def __init__(
        self,
        base_url: str = VLLM_BASE_URL,
        model: str = VLLM_MODEL,
        api_key: str = VLLM_API_KEY,
        timeout: int = VLLM_TIMEOUT,
        max_tokens: int = VLLM_MAX_TOKENS,
    ) -> None:
        self._base_url   = base_url.rstrip("/")
        self._model      = model
        self._api_key    = api_key
        self._timeout    = timeout
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        return self._model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, messages: list[dict], **kwargs) -> str:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("pip install httpx")

        payload = {
            "model":      self._model,
            "messages":   messages,
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", 0.1),
            "stream":     False,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            resp = await c.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def stream_chat(
        self, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str, None]:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("pip install httpx")

        payload = {
            "model":      self._model,
            "messages":   messages,
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "temperature": kwargs.get("temperature", 0.1),
            "stream":     True,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            async with c.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0]["delta"]
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError):
                        continue


def get_vllm_provider(async_mode: bool = False) -> VLLMProvider | AsyncVLLMProvider:
    """Factory — returns sync or async provider based on call context."""
    cls = AsyncVLLMProvider if async_mode else VLLMProvider
    return cls(
        base_url=VLLM_BASE_URL,
        model=VLLM_MODEL,
        api_key=VLLM_API_KEY,
        timeout=VLLM_TIMEOUT,
        max_tokens=VLLM_MAX_TOKENS,
    )
