from __future__ import annotations

"""
src/services/llm.py
LLM 调用薄包装层 — 所有实现已迁移到 LLMService。

保留此模块以维持对现有调用方的零改动兼容：
  from .llm import generate_answer, generate_answer_with_usage
"""
import logging
from .llm_service import get_llm_service

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一个航空制造工艺规范专家助手。"
    "请根据提供的规范内容，用中文准确回答问题。"
)

_ANSWER_TMPL = """\
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


def _build_messages(question: str, context: str, history: list[dict] | None = None) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for h in (history or [])[-12:]:
        role    = h.get("role", "user")
        content = h.get("content", "")
        if content.strip():
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": _ANSWER_TMPL.format(context=context, question=question)})
    return msgs


def generate_answer(
    question: str,
    context:  str,
    llm_mode:    str = "",
    llm_api_url: str = "",
    llm_api_key: str = "",
    llm_model:   str = "",
) -> str:
    """根据问题和上下文生成答案（向后兼容接口）。"""
    llm = get_llm_service()
    logger.info("调用 LLM model=%s", llm.model_name)
    try:
        return llm.chat(_build_messages(question, context))
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        return f"LLM 服务暂不可用（{e}），以下是检索到的相关章节：\n\n{context[:2000]}"


def generate_answer_with_usage(
    question: str,
    context:  str,
    history:  list[dict] | None = None,
    llm_mode:    str = "",
    llm_api_url: str = "",
    llm_api_key: str = "",
    llm_model:   str = "",
) -> tuple[str, dict]:
    """生成答案并返回 token 用量（向后兼容接口）。"""
    _empty_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    llm = get_llm_service()
    logger.info("调用 LLM model=%s", llm.model_name)
    try:
        return llm.chat_with_usage(_build_messages(question, context, history))
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        return (
            f"LLM 服务暂不可用（{e}），以下是检索到的相关章节：\n\n{context[:2000]}",
            _empty_usage,
        )
