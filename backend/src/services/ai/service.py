from __future__ import annotations

"""LLM service facade built on provider adapters."""

import logging
from typing import AsyncGenerator

from ...core.config import settings
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

    def __init__(self):
        self._settings = settings
        self._provider = self._build_provider()

    def _build_provider(self):
        s = self._settings
        mode = (s.LLM_MODE or "api").lower()
        provider = (s.LLM_PROVIDER or "").lower()

        if mode == "local":
            model_map = {
                "qwen": s.LOCAL_LLM_QWEN_MODEL or "qwen2.5:7b",
                "deepseek": s.LOCAL_LLM_DEEPSEEK_MODEL or "deepseek-r1:7b",
            }
            model = model_map.get(provider, s.OLLAMA_MODEL or "qwen2.5:7b")
            logger.info("LLMService -> 本地 Ollama provider=%s model=%s", provider or "generic", model)
            return OpenAICompatProvider(
                api_url=f"{s.OLLAMA_BASE_URL}/v1",
                api_key="ollama",
                model=model,
            )

        if provider == "anthropic":
            logger.info("LLMService -> Anthropic Claude model=%s", s.LLM_MODEL)
            return AnthropicProvider(api_key=s.LLM_API_KEY, model=s.LLM_MODEL)

        if provider == "qwen":
            model = s.LLM_QWEN_MODEL or "qwen-plus"
            logger.info("LLMService -> 通义千问 (DashScope) model=%s", model)
            return OpenAICompatProvider(
                api_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=s.DASHSCOPE_API_KEY,
                model=model,
            )

        if provider == "deepseek":
            model = s.LLM_DEEPSEEK_MODEL or "deepseek-chat"
            logger.info("LLMService -> DeepSeek API model=%s", model)
            return OpenAICompatProvider(
                api_url="https://api.deepseek.com/v1",
                api_key=s.DEEPSEEK_API_KEY,
                model=model,
            )

        if provider == "ernie":
            model = s.LLM_ERNIE_MODEL or "ernie-4.5-8k"
            logger.info("LLMService -> 文心一言 model=%s", model)
            return ErnieProvider(
                api_key=s.ERNIE_API_KEY,
                secret_key=s.ERNIE_SECRET_KEY,
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

    def chat(self, messages: list[dict], system_prompt: str = "", **kwargs) -> str:
        msgs = prepend_system(messages, system_prompt)
        try:
            return self._provider.chat(msgs, **kwargs)
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
            return self._provider.chat_with_usage(msgs, **kwargs)
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
            async for chunk in self._provider.stream_chat(msgs, **kwargs):
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


_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _service
    if _service is None:
        _service = LLMService()
    return _service

