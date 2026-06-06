from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from ..errors import trim_preview

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic Claude API"""

    def __init__(self, api_key: str, model: str):
        self._key = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def _build_payload(self, messages: list[dict], **kwargs) -> dict:
        system = ""
        non_system = []
        for message in messages:
            if message.get("role") == "system":
                system = message.get("content", "")
            else:
                non_system.append(message)
        payload: dict = {
            "model": self._model,
            "max_tokens": kwargs.pop("max_tokens", 2048),
            "messages": non_system,
        }
        if system:
            payload["system"] = system
        return payload

    def chat(self, messages: list[dict], **kwargs) -> str:
        import requests

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=self._build_payload(messages, **kwargs),
            timeout=kwargs.pop("timeout", 90),
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

    def chat_with_usage(self, messages: list[dict], **kwargs) -> tuple[str, dict]:
        import requests

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self._key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=self._build_payload(messages, **kwargs),
            timeout=kwargs.pop("timeout", 90),
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return data["content"][0]["text"], {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
        }

    async def stream_chat(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        import httpx

        payload = self._build_payload(messages, **kwargs)
        payload["stream"] = True
        async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 90)) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                saw_delta = False
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    try:
                        chunk = json.loads(data)
                        if chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {}).get("text", "")
                            if delta:
                                saw_delta = True
                                yield delta
                    except Exception:
                        logger.warning("Anthropic流式分片解析失败 model=%s chunk=%s", self._model, trim_preview(data))
                if not saw_delta:
                    raise RuntimeError(f"Anthropic 返回了空的流式响应 model={self._model}")
