from __future__ import annotations

"""LLM service facade built on provider adapters."""

import json
import logging
from typing import AsyncGenerator

from ...services.runtime.model_settings import get_runtime_settings_namespace
from .errors import LLMError, map_exception
from .providers import AnthropicProvider, ErnieProvider, OpenAICompatProvider

logger = logging.getLogger(__name__)


def prepend_system(messages: list[dict], system_prompt: str) -> list[dict]:
    if not system_prompt:
        return messages
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": system_prompt}] + list(messages)


class LLMService:
    """统一 LLM 服务。"""

    def __init__(self, runtime_settings=None):
        self._settings = runtime_settings or get_runtime_settings_namespace()
        self._provider = self._build_provider()

    def _build_provider(self):
        s = self._settings
        mode = (s.LLM_MODE or "api").lower()
        provider = (s.LLM_PROVIDER or "").lower()
        if provider in {"openai", "openai_compatible", "openai-compatible", "generic"}:
            provider = ""

        if mode == "local":
            model_map = {
                "qwen": s.LOCAL_LLM_QWEN_MODEL or "qwen2.5:7b",
                "deepseek": s.LOCAL_LLM_DEEPSEEK_MODEL or "deepseek-r1:7b",
            }
            model = s.LLM_MODEL or model_map.get(provider, s.OLLAMA_MODEL or "qwen2.5:7b")
            logger.info("LLMService -> 本地 Ollama provider=%s model=%s", provider or "generic", model)
            return OpenAICompatProvider(
                api_url=f"{s.OLLAMA_BASE_URL}/v1",
                api_key="ollama",
                model=model,
            )

        if provider == "anthropic":
            model = s.LLM_MODEL or "claude-3-5-sonnet-latest"
            logger.info("LLMService -> Anthropic Claude model=%s", model)
            return AnthropicProvider(api_key=s.LLM_API_KEY, model=model)

        if provider == "qwen":
            model = s.LLM_MODEL or s.LLM_QWEN_MODEL or "qwen-plus"
            logger.info("LLMService -> 通义千问 (DashScope) model=%s", model)
            return OpenAICompatProvider(
                api_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=s.LLM_API_KEY or s.DASHSCOPE_API_KEY,
                model=model,
            )

        if provider == "deepseek":
            model = s.LLM_MODEL or s.LLM_DEEPSEEK_MODEL or "deepseek-chat"
            logger.info("LLMService -> DeepSeek API model=%s", model)
            return OpenAICompatProvider(
                api_url="https://api.deepseek.com/v1",
                api_key=s.LLM_API_KEY or s.DEEPSEEK_API_KEY,
                model=model,
            )

        if provider == "ernie":
            model = s.LLM_MODEL or s.LLM_ERNIE_MODEL or "ernie-4.5-8k"
            logger.info("LLMService -> 文心一言 model=%s", model)
            return ErnieProvider(
                api_key=s.LLM_API_KEY or s.ERNIE_API_KEY,
                secret_key=getattr(s, "LLM_API_SECRET", "") or s.ERNIE_SECRET_KEY,
                model=model,
            )

        logger.info("LLMService -> 通用 OpenAI 兼容 url=%s model=%s", s.LLM_API_URL, s.LLM_MODEL)
        return OpenAICompatProvider(
            api_url=s.LLM_API_URL,
            api_key=s.LLM_API_KEY,
            model=s.LLM_MODEL,
        )

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    def _apply_defaults(self, kwargs: dict) -> dict:
        call_kwargs = dict(kwargs)
        call_kwargs.setdefault("timeout", self._settings.LLM_TIMEOUT)
        call_kwargs.setdefault("max_tokens", self._settings.LLM_MAX_TOKENS)
        return call_kwargs

    def chat(self, messages: list[dict], system_prompt: str = "", **kwargs) -> str:
        msgs = prepend_system(messages, system_prompt)
        try:
            return self._provider.chat(msgs, **self._apply_defaults(kwargs))
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("LLMService.chat 失败 provider=%s model=%s", type(self._provider).__name__, self.model_name)
            raise map_exception(exc) from exc

    def chat_with_usage(
        self,
        messages: list[dict],
        system_prompt: str = "",
        **kwargs,
    ) -> tuple[str, dict]:
        msgs = prepend_system(messages, system_prompt)
        try:
            return self._provider.chat_with_usage(msgs, **self._apply_defaults(kwargs))
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("LLMService.chat_with_usage 失败 provider=%s model=%s", type(self._provider).__name__, self.model_name)
            raise map_exception(exc) from exc

    async def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        msgs = prepend_system(messages, system_prompt)
        try:
            async for chunk in self._provider.stream_chat(msgs, **self._apply_defaults(kwargs)):
                yield chunk
        except LLMError:
            raise
        except Exception as exc:
            logger.exception(
                "LLMService.stream_chat 失败 provider=%s model=%s message_count=%d",
                type(self._provider).__name__,
                self.model_name,
                len(msgs),
            )
            raise map_exception(exc) from exc

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str = "",
        **kwargs,
    ) -> dict:
        msgs = prepend_system(messages, system_prompt)
        try:
            if isinstance(self._provider, OpenAICompatProvider):
                return await self._chat_with_tools_openai_compat(msgs, tools, **kwargs)
            if isinstance(self._provider, AnthropicProvider):
                return await self._chat_with_tools_anthropic(msgs, tools, **kwargs)
            text = self.chat(msgs, **kwargs)
            return {"text": text}
        except LLMError:
            raise
        except Exception as exc:
            logger.exception(
                "LLMService.chat_with_tools 失败 provider=%s model=%s",
                type(self._provider).__name__,
                self.model_name,
            )
            raise map_exception(exc) from exc

    async def _chat_with_tools_openai_compat(
        self,
        messages: list[dict],
        tools: list[dict],
        **kwargs,
    ) -> dict:
        import requests

        provider = self._provider
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        resp = await self._run_in_thread(
            requests.post,
            f"{provider._url}/chat/completions",
            headers={
                "Authorization": f"Bearer {provider._key}",
                "Content-Type": "application/json",
            },
            json={
                "model": kwargs.pop("model", provider.model_name),
                "messages": messages,
                "tools": tool_defs,
                "tool_choice": "auto",
                "stream": False,
                **kwargs,
            },
            timeout=kwargs.pop("timeout", self._settings.LLM_TIMEOUT),
        )
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            tc = tool_calls[0]
            arguments = tc.get("function", {}).get("arguments", "{}")
            try:
                tool_input = json.loads(arguments) if isinstance(arguments, str) else arguments
            except Exception:
                tool_input = {}
            return {
                "tool_use": {
                    "name": tc.get("function", {}).get("name", ""),
                    "input": tool_input,
                    "id": tc.get("id", ""),
                },
                "text": msg.get("content") or "",
            }
        return {"text": msg.get("content") or ""}

    async def _chat_with_tools_anthropic(
        self,
        messages: list[dict],
        tools: list[dict],
        **kwargs,
    ) -> dict:
        import requests

        provider = self._provider
        system = ""
        non_system = []
        for message in messages:
            if message.get("role") == "system":
                system = message.get("content", "")
            else:
                non_system.append(message)
        payload = provider._build_payload(non_system, **kwargs)
        if system:
            payload["system"] = system
        payload["tools"] = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in tools
        ]
        payload["tool_choice"] = {"type": "auto"}
        resp = await self._run_in_thread(
            requests.post,
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": provider._key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=kwargs.pop("timeout", self._settings.LLM_TIMEOUT),
        )
        resp.raise_for_status()
        data = resp.json()
        tool_use = None
        text_parts: list[str] = []
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and tool_use is None:
                tool_use = {
                    "name": block.get("name", ""),
                    "input": block.get("input", {}),
                    "id": block.get("id", ""),
                }
            elif block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        result = {"text": "".join(text_parts)}
        if tool_use:
            result["tool_use"] = tool_use
        return result

    async def _run_in_thread(self, func, *args, **kwargs):
        import asyncio

        return await asyncio.to_thread(func, *args, **kwargs)

def get_llm_service() -> LLMService:
    return LLMService(get_runtime_settings_namespace())
