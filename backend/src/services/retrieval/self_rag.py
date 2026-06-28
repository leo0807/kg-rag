"""
Self-RAG — self-reflective retrieval-augmented generation.

The model judges: should I retrieve? Is this retrieved content relevant?
Does the final answer have support? Uses special reflection tokens:
  [Retrieve] / [No Retrieve]
  [Relevant] / [Irrelevant]
  [Supported] / [Not Supported] / [Partially Supported]

Implementation: Prompt-based simulation of Self-RAG reflection tokens.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)


def _needs_retrieval(question: str, llm_svc) -> bool:
    """Ask LLM whether retrieval is needed for this question."""
    try:
        resp = llm_svc.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "判断以下问题是否需要查询外部知识库才能准确回答。"
                        "如果需要查询，回复 [Retrieve]；否则回复 [No Retrieve]。"
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=20,
            timeout=10,
        )
        return "[Retrieve]" in resp
    except Exception:
        return True  # Default to retrieve


def _is_relevant(question: str, chunk_content: str, llm_svc) -> bool:
    """Judge whether a retrieved chunk is relevant to the question."""
    try:
        resp = llm_svc.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "判断以下文档片段是否与问题相关。"
                        "相关回复 [Relevant]，不相关回复 [Irrelevant]。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"问题: {question}\n\n文档片段: {chunk_content[:500]}",
                },
            ],
            max_tokens=20,
            timeout=10,
        )
        return "[Relevant]" in resp
    except Exception:
        return True  # Default to relevant


def _check_support(answer: str, sources: list[dict], llm_svc) -> str:
    """Check if the generated answer is supported by the sources."""
    contexts = "\n".join(s.get("content", "")[:300] for s in sources[:3])
    try:
        resp = llm_svc.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "判断以下回答是否有来源文档支持。\n"
                        "完全支持: [Supported]\n"
                        "部分支持: [Partially Supported]\n"
                        "不支持: [Not Supported]"
                    ),
                },
                {
                    "role": "user",
                    "content": f"回答: {answer[:500]}\n\n来源文档:\n{contexts}",
                },
            ],
            max_tokens=30,
            timeout=10,
        )
        if "[Supported]" in resp:
            return "supported"
        if "[Partially Supported]" in resp:
            return "partial"
        return "unsupported"
    except Exception:
        return "unknown"


async def self_rag_query(question: str, retriever, generator,
                          max_retry: int = 2) -> dict[str, Any]:
    """
    Execute a Self-RAG pipeline.

    Args:
        question: User question
        retriever: Async retriever returning list of source dicts
        generator: Callable(question, sources) → answer string
        max_retry: How many times to retry on low-support answer

    Returns:
        {answer, sources, support_level, retrieval_used, retries}
    """
    from ..ai.llm_service import get_llm_service
    llm_svc = get_llm_service()

    # Step 1: Judge if retrieval is needed
    needs_retrieval = _needs_retrieval(question, llm_svc)

    if not needs_retrieval:
        log.info("Self-RAG: [No Retrieve] for question")
        answer = generator(question, [])
        return {
            "answer": answer,
            "sources": [],
            "support_level": "no_retrieval",
            "retrieval_used": False,
            "retries": 0,
        }

    # Step 2: Retrieve and filter relevant chunks
    sources = await retriever(question, top_k=10)
    relevant_sources = [
        s for s in sources
        if _is_relevant(question, s.get("content", ""), llm_svc)
    ]
    log.info("Self-RAG: %d/%d chunks relevant", len(relevant_sources), len(sources))

    if not relevant_sources:
        relevant_sources = sources[:3]  # Fallback to top-3 if all filtered

    # Step 3: Generate answer
    answer = generator(question, relevant_sources[:5])

    # Step 4: Check support
    support = _check_support(answer, relevant_sources, llm_svc)
    retries = 0

    # Step 5: Retry if not supported
    while support == "unsupported" and retries < max_retry:
        log.info("Self-RAG: [Not Supported], retry %d/%d", retries + 1, max_retry)
        more_sources = await retriever(question, top_k=20)
        if len(more_sources) > len(sources):
            relevant_sources = more_sources[:5]
            answer = generator(question, relevant_sources)
            support = _check_support(answer, relevant_sources, llm_svc)
        retries += 1

    return {
        "answer": answer,
        "sources": relevant_sources[:5],
        "support_level": support,
        "retrieval_used": True,
        "retries": retries,
    }
