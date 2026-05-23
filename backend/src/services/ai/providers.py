from __future__ import annotations

"""Concrete LLM provider adapters."""

import json
import logging
from typing import AsyncGenerator

from .errors import parse_response_for_business_error, trim_preview

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


class ErnieProvider:
    """百度文心一言（ERNIE）"""

    def __init__(self, api_key: str, secret_key: str, model: str = "ernie-4.5-8k"):
        self._api_key = api_key
        self._secret_key = secret_key
        self._model = model
        self._access_token = ""

    @property
    def model_name(self) -> str:
        return self._model

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        import requests

        resp = requests.post(
            "https://aip.baidubce.com/oauth/2.0/token",
            params={
                "grant_type": "client_credentials",
                "client_id": self._api_key,
                "client_secret": self._secret_key,
            },
            timeout=10,
        )
        self._access_token = resp.json()["access_token"]
        return self._access_token

    def chat(self, messages: list[dict], **kwargs) -> str:
        import requests

        token = self._get_access_token()
        resp = requests.post(
            f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self._model}",
            params={"access_token": token},
            headers={"Content-Type": "application/json"},
            json={"messages": [m for m in messages if m.get("role") != "system"]},
            timeout=kwargs.pop("timeout", 90),
        )
        resp.raise_for_status()
        body = resp.json()
        if "result" not in body:
            raise RuntimeError(f"文心一言无 result: {body.get('error_msg', body)}")
        return body["result"]

    def chat_with_usage(self, messages: list[dict], **kwargs) -> tuple[str, dict]:
        import requests

        token = self._get_access_token()
        resp = requests.post(
            f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self._model}",
            params={"access_token": token},
            headers={"Content-Type": "application/json"},
            json={"messages": [m for m in messages if m.get("role") != "system"]},
            timeout=kwargs.pop("timeout", 90),
        )
        resp.raise_for_status()
        body = resp.json()
        if "result" not in body:
            raise RuntimeError(f"文心一言无 result: {body.get('error_msg', body)}")
        usage = body.get("usage", {})
        return body["result"], {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }

    async def stream_chat(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        import httpx

        token = self._get_access_token()
        async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 90)) as client:
            async with client.stream(
                "POST",
                f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self._model}",
                params={"access_token": token},
                headers={"Content-Type": "application/json"},
                json={
                    "messages": [m for m in messages if m.get("role") != "system"],
                    "stream": True,
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
                        text = chunk.get("result", "")
                        if text:
                            saw_delta = True
                            yield text
                    except Exception:
                        logger.warning("ERNIE流式分片解析失败 model=%s chunk=%s", self._model, trim_preview(data))
                if not saw_done and not saw_delta:
                    raise RuntimeError(f"ERNIE 返回了空的流式响应 model={self._model}")

