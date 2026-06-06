from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from ..errors import trim_preview

logger = logging.getLogger(__name__)


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
