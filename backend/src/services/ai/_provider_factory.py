from __future__ import annotations

import logging

from .providers import AnthropicProvider, ErnieProvider, OpenAICompatProvider

logger = logging.getLogger(__name__)


def _build_llm_provider(s):
    mode     = (s.LLM_MODE     or "api").lower()
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
