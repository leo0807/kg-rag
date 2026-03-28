"""
src/services/llm.py
LLM 服务，支持多种接入方式
- OpenAI 兼容 API（Ollama、vLLM、LMStudio、硅基流动、DeepSeek 等）
- Anthropic Claude API
"""
import logging
import requests
from ..core.config import settings

logger = logging.getLogger(__name__)


def _call_openai_compatible(
    prompt:   str,
    api_url:  str,
    api_key:  str,
    model:    str,
    timeout:  int = 60,
) -> str:
    """调用 OpenAI 兼容的 Chat Completion API"""
    res = requests.post(
        f"{api_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        json={
            "model":    model,
            "messages": [{"role": "user", "content": prompt}],
            "stream":   False,
        },
        timeout=timeout,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def _call_anthropic(
    prompt:  str,
    api_key: str,
    model:   str,
    timeout: int = 60,
) -> str:
    """调用 Anthropic Claude API"""
    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        },
        json={
            "model":      model,
            "max_tokens": 2048,
            "messages":   [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    res.raise_for_status()
    return res.json()["content"][0]["text"]


def generate_answer(
    question: str,
    context:  str,
    llm_mode:    str = "",
    llm_api_url: str = "",
    llm_api_key: str = "",
    llm_model:   str = "",
) -> str:
    """
    根据问题和上下文生成答案
    优先使用传入的配置，否则使用全局配置
    """
    mode    = llm_mode    or settings.LLM_MODE
    api_url = llm_api_url or settings.LLM_API_URL
    api_key = llm_api_key or settings.LLM_API_KEY
    model   = llm_model   or settings.LLM_MODEL

    prompt = f"""你是一个航空制造工艺规范专家助手。请根据以下工艺规范文档内容，用中文回答用户的问题。

## 相关工艺规范内容

{context}

## 用户问题

{question}

## 回答要求

1. 只根据上述规范内容回答，不要添加规范中没有的信息
2. 如果规范中没有相关内容，请说明"在提供的规范中未找到相关信息"
3. 回答要简洁清晰，重点突出
4. 引用具体章节时请标注章节号

请回答："""

    logger.info("调用 LLM mode=%s model=%s", mode, model)

    try:
        if mode == "anthropic":
            return _call_anthropic(prompt, api_key, model)
        else:
            # OpenAI 兼容模式（包括 Ollama、vLLM、硅基流动等）
            return _call_openai_compatible(prompt, api_url, api_key, model)
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        # 降级：返回原始检索结果
        return f"LLM 服务暂不可用（{e}），以下是检索到的相关章节：\n\n{context[:2000]}"