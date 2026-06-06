from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from ..errors import parse_response_for_business_error, trim_preview

logger = logging.getLogger(__name__)


class OpenAICompatProvider:
    """通用 OpenAI 兼容端点（Ollama / vLLM / DeepSeek / 通义千问等）"""

    def __init__(self, api_url: str, api_key: str, model: str):
        self._url = api_url.rstrip("/")
        self._key = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def chat(self, messages: list[dict], **kwargs) -> str:
        import requests

        model = kwargs.pop("model", self._model)
        timeout = kwargs.pop("timeout", 90)
        resp = requests.post(
            f"{self._url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": False, **kwargs},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        biz_err = parse_response_for_business_error(data)
        if biz_err:
            raise biz_err
        return data["choices"][0]["message"]["content"]

    def chat_with_usage(self, messages: list[dict], **kwargs) -> tuple[str, dict]:
        import requests

        model = kwargs.pop("model", self._model)
        timeout = kwargs.pop("timeout", 90)
        resp = requests.post(
            f"{self._url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": False, **kwargs},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        biz_err = parse_response_for_business_error(data)
        if biz_err:
            raise biz_err
        usage = data.get("usage", {})
        return data["choices"][0]["message"]["content"], {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }

    async def stream_chat(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        import httpx

        model = kwargs.pop("model", self._model)
        timeout = kwargs.pop("timeout", 90)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self._url}/chat/completions",
                headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    **kwargs,
                },
            ) as response:
                response.raise_for_status()
                saw_done = False
                saw_delta = False
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        saw_done = True
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get("usage") and not chunk.get("choices"):
                            continue
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            saw_delta = True
                            yield delta
                    except Exception:
                        logger.warning("OpenAI兼容流式分片解析失败 model=%s chunk=%s", model, trim_preview(data))
                if not saw_done and not saw_delta:
                    raise RuntimeError(f"上游返回了空的流式响应 model={model}")
