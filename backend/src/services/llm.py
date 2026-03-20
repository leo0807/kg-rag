import logging
from collections.abc import Generator
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from ..core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是航空工艺规范知识库的专业助手。
请仅根据以下参考章节回答问题，不要使用你自己的背景知识补充内容。
如果参考章节中没有足够信息，请明确回答"在提供的文件中未找到相关内容"。
引用具体内容时请注明章节号（如 § 3.2.1）。"""


def _build_messages(question: str, context: str) -> list:
    human_text = f"参考章节：\n\n{context}\n\n问题：{question}"
    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=human_text),
    ]


def _get_llm() -> ChatOllama:
    return ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0,
    )


def generate(question: str, context: str) -> str:
    """一次性调用，返回完整答案字符串（用于非流式场景）。"""
    logger.info("调用 LLM model=%s", settings.OLLAMA_MODEL)
    response = _get_llm().invoke(_build_messages(question, context))
    return response.content


def generate_stream(question: str, context: str) -> Generator[str, None, None]:
    """
    流式调用，逐个 yield LLM 输出的文本片段（chunk）。

    ChatOllama.stream() 返回一个迭代器，每次迭代拿到一个
    AIMessageChunk 对象，其 .content 是这一帧的文本片段。
    片段大小由 Ollama 决定，通常是 1～几个 token。
    """
    logger.info("流式调用 LLM model=%s", settings.OLLAMA_MODEL)
    for chunk in _get_llm().stream(_build_messages(question, context)):
        if chunk.content:
            yield chunk.content
