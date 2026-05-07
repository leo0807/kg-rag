from __future__ import annotations

"""
src/services/llm.py
LLM 调用薄包装层 — 所有实现已迁移到 LLMService。

保留此模块以维持对现有调用方的零改动兼容：
  from .llm import generate_answer, generate_answer_with_usage
"""
import logging
import re
from .llm_service import get_llm_service

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一个航空制造工艺规范专家助手。"
    "请根据提供的规范内容，用中文准确回答问题。"
    "回答时优先使用来源中的直接定义和描述，不要过多展开次要细节。"
    "如果问题询问'特性'或'性质'，优先引用定义类章节（术语定义、基本要求章节），"
    "而不是参数表格。"
)


def clean_llm_response(text: str | None) -> str:
    if not text:
        return ""
    text = text.replace("\ufffd", "")
    text = re.sub(r"([。，、；：！？])\1+", r"\1", text)
    text = re.sub(r"。+", "。", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_ANSWER_TMPL = """\
## 相关工艺规范内容

{context}

## 用户问题

{question}

## 回答要求

1. 只根据上述规范内容回答，不要添加规范中没有的信息
2. 如果上下文中存在与问题相关的参数、数值或同义表达，即使问题中的词语没有完全一致，也要优先据此回答
3. 只有当上下文确实没有可用信息时，才说明"在提供的规范中未找到相关信息"
4. 对工艺参数问题，请按"初始压力 / 维持真空度 / 温度 / 时间"这类维度直接列出原文中的数值，不要擅自改写符号或跨章节拼接
5. 如果问题询问特性或性质，优先提炼定义类语句中的核心特征词（例如粘性、弹性），不要被参数型描述带偏
6. 如果来源中出现 "soft and ductile paste"、"solid and elastic rubber" 之类表述，可直接概括为"粘性和弹性"
7. 回答要简洁清晰，重点突出，尤其要优先提取温度、压力、时间等数值参数
8. 引用具体章节时请标注章节号

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
        return clean_llm_response(llm.chat(_build_messages(question, context)))
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
        return clean_llm_response(answer), usage
    except Exception as e:
        logger.error("LLM 调用失败: %s", e)
        return (
            f"LLM 服务暂不可用（{e}），以下是检索到的相关章节：\n\n{context[:2000]}",
            _empty_usage,
        )
