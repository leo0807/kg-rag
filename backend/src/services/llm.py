import logging
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from ..core.config import settings

logger = logging.getLogger(__name__)

# System prompt 固定了 LLM 的角色和回答规则：
# - 只能引用提供的上下文，不能凭空捏造
# - 如果上下文不足，明确说"文件中未找到"
# - 引用时注明来源章节号，方便工程师溯源
_SYSTEM_PROMPT = """你是航空工艺规范知识库的专业助手。
请仅根据以下参考章节回答问题，不要使用你自己的背景知识补充内容。
如果参考章节中没有足够信息，请明确回答"在提供的文件中未找到相关内容"。
引用具体内容时请注明章节号（如 § 3.2.1）。"""


def _get_llm() -> ChatOllama:
    # ChatOllama 是无状态的，每次调用都可以新建，不需要单例
    return ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        temperature=0,        # 设为 0：技术问答需要确定性，不需要创造性
    )


def generate(question: str, context: str) -> str:
    """
    把问题和检索到的上下文发给 Ollama，返回 LLM 生成的答案字符串。

    消息结构：
    - SystemMessage：设定角色和约束
    - HumanMessage：把 context 和 question 拼在一起发送
    """
    llm = _get_llm()

    human_text = f"参考章节：\n\n{context}\n\n问题：{question}"

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=human_text),
    ]

    logger.info("调用 LLM model=%s", settings.OLLAMA_MODEL)
    response = llm.invoke(messages)

    return response.content
