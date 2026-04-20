"""
backend/src/services/llm_service.py
统一 LLM 服务层

通过环境变量控制提供方，屏蔽所有下层 HTTP 细节：

  LLM_MODE=api  + LLM_PROVIDER=qwen       → 通义千问 (DashScope OpenAI 兼容端点)
  LLM_MODE=api  + LLM_PROVIDER=ernie      → 文心一言 (百度 AI 开放平台)
  LLM_MODE=api  + LLM_PROVIDER=deepseek   → DeepSeek API
  LLM_MODE=api  + LLM_PROVIDER=anthropic  → Anthropic Claude API
  LLM_MODE=api  + LLM_PROVIDER=""         → 通用 OpenAI 兼容端点 (LLM_API_URL/KEY/MODEL)

  LLM_MODE=local + LLM_PROVIDER=qwen      → 本地 Qwen2.5（via Ollama）
  LLM_MODE=local + LLM_PROVIDER=deepseek  → 本地 DeepSeek（via Ollama）
  LLM_MODE=local + LLM_PROVIDER=""        → Ollama 通用（OLLAMA_BASE_URL / OLLAMA_MODEL）

主要接口：
  llm.chat(messages, system_prompt)           → str
  llm.chat_with_usage(messages, system_prompt) → (str, {"prompt_tokens": int, "completion_tokens": int})
  llm.stream_chat(messages)                    → AsyncGenerator[str, None]
  llm.model_name                               → str  (当前使用的模型名称，供观测层记录)
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 结构化错误类型
# ─────────────────────────────────────────────────────────────────────────────

class LLMError(Exception):
    """LLM 调用失败，携带用户可见的错误码和消息。"""

    def __init__(
        self,
        code:        str,
        message:     str,
        status_code: int | None = None,
        endpoint:    str        = "",
    ):
        super().__init__(message)
        self.code        = code
        self.message     = message
        self.status_code = status_code   # 原始 HTTP 状态码（管理员可见）
        self.endpoint    = endpoint      # 失败的 API 端点（管理员可见）


def _map_exception(exc: Exception, endpoint: str = "") -> LLMError:
    """将底层异常映射为 LLMError，便于上层统一处理。"""
    try:
        import requests as _req
        _req_http  = _req.HTTPError
        _req_to    = _req.exceptions.Timeout
        _req_conn  = _req.exceptions.ConnectionError
    except ImportError:
        _req_http = _req_to = _req_conn = type(None)  # type: ignore[assignment]

    try:
        import httpx as _httpx
        _hx_http = _httpx.HTTPStatusError
        _hx_to   = _httpx.TimeoutException
        _hx_conn = _httpx.ConnectError
    except ImportError:
        _hx_http = _hx_to = _hx_conn = type(None)  # type: ignore[assignment]

    # 已经是 LLMError，直接返回
    if isinstance(exc, LLMError):
        return exc

    # 提取 HTTP 状态码
    status: int | None = None
    if isinstance(exc, _req_http) and getattr(exc, "response", None) is not None:
        status = exc.response.status_code  # type: ignore[union-attr]
    elif isinstance(exc, _hx_http):
        status = exc.response.status_code  # type: ignore[union-attr]

    if status == 403:
        return LLMError("quota_exceeded",      "API 额度不足，请联系管理员充值",    status_code=status, endpoint=endpoint)
    if status == 429:
        return LLMError("rate_limited",        "请求过于频繁，请稍后再试",          status_code=status, endpoint=endpoint)
    if status in (408, 504):
        return LLMError("timeout",             "模型响应超时，请重试",              status_code=status, endpoint=endpoint)
    if status is not None:
        return LLMError("unknown_error",       "AI 服务异常，请联系管理员",         status_code=status, endpoint=endpoint)

    if isinstance(exc, (_req_to, _hx_to)):
        return LLMError("timeout",             "模型响应超时，请重试",              endpoint=endpoint)
    if isinstance(exc, (_req_conn, _hx_conn)):
        return LLMError("service_unavailable", "AI 服务暂时不可用，请稍后再试",     endpoint=endpoint)

    return LLMError("unknown_error",           "AI 服务异常，请联系管理员",         endpoint=endpoint)


# ─────────────────────────────────────────────────────────────────────────────
# 底层提供方
# ─────────────────────────────────────────────────────────────────────────────

class _OpenAICompatProvider:
    """通用 OpenAI 兼容端点（Ollama / vLLM / 硅基流动 / DeepSeek / 通义千问等）"""

    def __init__(self, api_url: str, api_key: str, model: str):
        self._url   = api_url.rstrip("/")
        self._key   = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def chat(self, messages: list[dict], **kwargs) -> str:
        import requests
        model   = kwargs.pop("model",   self._model)
        timeout = kwargs.pop("timeout", 90)
        resp = requests.post(
            f"{self._url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": False, **kwargs},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def chat_with_usage(self, messages: list[dict], **kwargs) -> tuple[str, dict]:
        import requests
        model   = kwargs.pop("model",   self._model)
        timeout = kwargs.pop("timeout", 90)
        resp = requests.post(
            f"{self._url}/chat/completions",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "stream": False, **kwargs},
            timeout=timeout,
        )
        resp.raise_for_status()
        data   = resp.json()
        text   = data["choices"][0]["message"]["content"]
        usage  = data.get("usage", {})
        return text, {
            "prompt_tokens":     usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }

    async def stream_chat(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        import httpx
        model   = kwargs.pop("model",   self._model)
        timeout = kwargs.pop("timeout", 90)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self._url}/chat/completions",
                headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                json={
                    "model":          model,
                    "messages":       messages,
                    "stream":         True,
                    "stream_options": {"include_usage": True},
                    **kwargs,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get("usage") and not chunk.get("choices"):
                            continue
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        pass


class _AnthropicProvider:
    """Anthropic Claude API"""

    def __init__(self, api_key: str, model: str):
        self._key   = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def _build_payload(self, messages: list[dict], **kwargs) -> dict:
        # 分离 system 消息
        system = ""
        non_system = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content", "")
            else:
                non_system.append(m)
        payload: dict = {
            "model":      self._model,
            "max_tokens": kwargs.pop("max_tokens", 2048),
            "messages":   non_system,
        }
        if system:
            payload["system"] = system
        return payload

    def chat(self, messages: list[dict], **kwargs) -> str:
        import requests
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         self._key,
                "anthropic-version": "2023-06-01",
                "Content-Type":      "application/json",
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
                "x-api-key":         self._key,
                "anthropic-version": "2023-06-01",
                "Content-Type":      "application/json",
            },
            json=self._build_payload(messages, **kwargs),
            timeout=kwargs.pop("timeout", 90),
        )
        resp.raise_for_status()
        data  = resp.json()
        text  = data["content"][0]["text"]
        usage = data.get("usage", {})
        return text, {
            "prompt_tokens":     usage.get("input_tokens",  0),
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
                    "x-api-key":         self._key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type":      "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    try:
                        chunk = json.loads(data)
                        if chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {}).get("text", "")
                            if delta:
                                yield delta
                    except Exception:
                        pass


class _ErnieProvider:
    """百度文心一言（ERNIE）— 使用百度 AI 开放平台 OpenAI 兼容端点"""

    def __init__(self, api_key: str, secret_key: str, model: str = "ernie-4.5-8k"):
        self._api_key    = api_key
        self._secret_key = secret_key
        self._model      = model
        self._access_token: str = ""

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
                "grant_type":    "client_credentials",
                "client_id":     self._api_key,
                "client_secret": self._secret_key,
            },
            timeout=10,
        )
        self._access_token = resp.json()["access_token"]
        return self._access_token

    def chat(self, messages: list[dict], **kwargs) -> str:
        import requests
        token = self._get_access_token()
        resp  = requests.post(
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
        resp  = requests.post(
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
            "prompt_tokens":     usage.get("prompt_tokens",     0),
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
                    "stream":   True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        text = chunk.get("result", "")
                        if text:
                            yield text
                    except Exception:
                        pass


# ─────────────────────────────────────────────────────────────────────────────
# LLMService — 统一入口
# ─────────────────────────────────────────────────────────────────────────────

class LLMService:
    """
    统一 LLM 服务。

    实例化后通过以下方法调用：
      .chat(messages, system_prompt="") → str
      .chat_with_usage(messages, system_prompt="") → (str, usage_dict)
      .stream_chat(messages) → AsyncGenerator[str, None]
      .model_name → str
    """

    def __init__(self):
        from ..core.config import settings
        self._settings  = settings
        self._provider  = self._build_provider()

    def _build_provider(self):
        s        = self._settings
        mode     = (s.LLM_MODE     or "api").lower()
        provider = (s.LLM_PROVIDER or "").lower()

        if mode == "local":
            # 本地模式 → Ollama
            model_map = {
                "qwen":     s.LOCAL_LLM_QWEN_MODEL     or "qwen2.5:7b",
                "deepseek": s.LOCAL_LLM_DEEPSEEK_MODEL or "deepseek-r1:7b",
            }
            model = model_map.get(provider, s.OLLAMA_MODEL or "qwen2.5:7b")
            logger.info("LLMService → 本地 Ollama provider=%s model=%s", provider or "generic", model)
            return _OpenAICompatProvider(
                api_url = f"{s.OLLAMA_BASE_URL}/v1",
                api_key = "ollama",
                model   = model,
            )

        # API 模式
        if provider == "anthropic":
            logger.info("LLMService → Anthropic Claude model=%s", s.LLM_MODEL)
            return _AnthropicProvider(api_key=s.LLM_API_KEY, model=s.LLM_MODEL)

        if provider == "qwen":
            model = s.LLM_QWEN_MODEL or "qwen-plus"
            logger.info("LLMService → 通义千问 (DashScope) model=%s", model)
            return _OpenAICompatProvider(
                api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key = s.DASHSCOPE_API_KEY,
                model   = model,
            )

        if provider == "deepseek":
            model = s.LLM_DEEPSEEK_MODEL or "deepseek-chat"
            logger.info("LLMService → DeepSeek API model=%s", model)
            return _OpenAICompatProvider(
                api_url = "https://api.deepseek.com/v1",
                api_key = s.DEEPSEEK_API_KEY,
                model   = model,
            )

        if provider == "ernie":
            model = s.LLM_ERNIE_MODEL or "ernie-4.5-8k"
            logger.info("LLMService → 文心一言 model=%s", model)
            return _ErnieProvider(
                api_key    = s.ERNIE_API_KEY,
                secret_key = s.ERNIE_SECRET_KEY,
                model      = model,
            )

        # 默认：通用 OpenAI 兼容（向后兼容旧 LLM_API_URL/KEY/MODEL 配置）
        logger.info("LLMService → 通用 OpenAI 兼容 url=%s model=%s", s.LLM_API_URL, s.LLM_MODEL)
        return _OpenAICompatProvider(
            api_url = s.LLM_API_URL,
            api_key = s.LLM_API_KEY,
            model   = s.LLM_MODEL,
        )

    # ── 公共接口 ────────────────────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    def chat(
        self,
        messages:      list[dict],
        system_prompt: str = "",
        **kwargs,
    ) -> str:
        """同步调用，返回 LLM 回复文本。失败时抛出 LLMError。"""
        msgs = _prepend_system(messages, system_prompt)
        try:
            return self._provider.chat(msgs, **kwargs)
        except LLMError:
            raise
        except Exception as e:
            logger.error("LLMService.chat 失败: %s", e)
            raise _map_exception(e) from e

    def chat_with_usage(
        self,
        messages:      list[dict],
        system_prompt: str = "",
        **kwargs,
    ) -> tuple[str, dict]:
        """同步调用，返回 (文本, token 用量字典)。失败时抛出 LLMError。"""
        msgs = _prepend_system(messages, system_prompt)
        try:
            return self._provider.chat_with_usage(msgs, **kwargs)
        except LLMError:
            raise
        except Exception as e:
            logger.error("LLMService.chat_with_usage 失败: %s", e)
            raise _map_exception(e) from e

    async def stream_chat(
        self,
        messages:      list[dict],
        system_prompt: str = "",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """异步流式调用，yield 每个 token 片段。失败时抛出 LLMError。"""
        msgs = _prepend_system(messages, system_prompt)
        try:
            async for chunk in self._provider.stream_chat(msgs, **kwargs):
                yield chunk
        except LLMError:
            raise
        except Exception as e:
            logger.error("LLMService.stream_chat 失败: %s", e)
            raise _map_exception(e) from e


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _prepend_system(messages: list[dict], system_prompt: str) -> list[dict]:
    """若提供 system_prompt 且消息列表里没有 system 角色，则插到最前面。"""
    if not system_prompt:
        return messages
    # 如果第一条已经是 system，不重复插入
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": system_prompt}] + list(messages)


# ─────────────────────────────────────────────────────────────────────────────
# 模块级单例
# ─────────────────────────────────────────────────────────────────────────────

_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """获取全局 LLMService 单例（首次调用时初始化）。"""
    global _service
    if _service is None:
        _service = LLMService()
    return _service
