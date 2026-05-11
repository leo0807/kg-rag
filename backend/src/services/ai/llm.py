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

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一个航空制造工艺规范专家助手。"
    "请根据提供的规范内容，用中文准确回答问题。"
    "回答时优先使用来源中的直接定义和描述，不要过多展开次要细节。"
    "如果问题询问'特性'或'性质'，优先引用定义类章节（术语定义、基本要求章节），"
    "而不是参数表格。"
    "重要：规范编号必须与来源章节完全一致，不得自行修改或补全。"
    "如果来源中没有某个规范的相关内容，必须明确说未找到该规范的相关内容，"
    "不得自行补充、猜测或把其他规范编号替换进来。"
    "来源内容中可能存在 OCR 扫描乱码（如 isis、isN、NN 等），"
    "回答时跳过这些乱码，只提取周围可读的有效信息，不要在答案中重复乱码。"
)


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
9. 如果是比较两个或多个规范，不要因为某一份规范未检到内容就下结论说“并无区别”；
   应明确写出“当前检索结果未找到该规范的直接相关内容”，并避免用其他规范的内容替代。
10. 不要自行补全、猜测或编造不存在的规范编号，规范编号必须和来源完全一致

请回答："""


def _build_messages(question: str, context: str, history: list[dict] | None = None) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for h in trim_conversation_history_for_question(question, history, max_rounds=3):
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
