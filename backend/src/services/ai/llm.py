from __future__ import annotations

"""
src/services/llm.py
LLM 调用薄包装层 — 所有实现已迁移到 LLMService。

保留此模块以维持对现有调用方的零改动兼容：
  from .llm import generate_answer, generate_answer_with_usage
"""
import logging
import re
from ..answer_humanizer import humanize_answer_text
from .llm_service import get_llm_service
from ..context_utils import trim_conversation_history_for_question
from ..prompts import registry

logger = logging.getLogger(__name__)

def clean_llm_response(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("```", "")
    text = text.replace("\ufffd", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])(?![Cc][Pp][Ss])[A-Za-z]{2,12}(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])(?![Cc][Pp][Ss])[A-Za-z]{2,12}(?=\s*[0-9])", "", text)
    text = re.sub(r"(?m)^(#{1,6})(\S)", r"\1 \2", text)
    text = re.sub(r"(#{1,6}\s+[^#\n]+)#{2,}", r"\1\n\n", text)
    text = re.sub(r"([。！？；:：])\s*(?=(?:###|-\s|\d{1,3}\.))", r"\1\n\n", text)
    text = re.sub(r"(?<!\n)(\d{1,3}\.\s*)(?=[^\d])", r"\n\1", text)
    text = re.sub(r"(?<!\n)([-•]\s+)", r"\n\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"([。，、；：！？])\1+", r"\1", text)
    text = re.sub(r"。+", "。", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_messages(question: str, context: str, history: list[dict] | None = None) -> list[dict]:
    rendered = registry.render("qa_general", sources=context, question=question)
    msgs: list[dict] = [{"role": "system", "content": rendered["system"]}]
    for h in trim_conversation_history_for_question(question, history, max_rounds=3):
        role    = h.get("role", "user")
        content = h.get("content", "")
        if content.strip():
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": rendered["user"]})
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
        return humanize_answer_text(clean_llm_response(llm.chat(_build_messages(question, context))), question)
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
        answer, usage = llm.chat_with_usage(_build_messages(question, context, history))
        return humanize_answer_text(clean_llm_response(answer), question), usage
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        return (
            f"LLM 服务暂不可用（{e}），以下是检索到的相关章节：\n\n{context[:2000]}",
            _empty_usage,
        )
