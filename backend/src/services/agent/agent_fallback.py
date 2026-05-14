from __future__ import annotations

import re

from .agent_helpers import compose_compare_answer, dedupe_images, dedupe_sections, is_compare_question, summarize_sources


def _extract_doc_ids(question: str) -> list[str]:
    return re.findall(r"CPS\d{3,4}", question.upper())


def _extract_topic(question: str) -> str:
    topic = re.sub(r"CPS\d{3,4}", "", question)
    topic = re.sub(r"[和与及,，。？?比较不同差异区别有什么]", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip()
    return topic or "相关要求"


async def parallel_rrf_fallback(question: str, tool_executor) -> dict:
    doc_ids = _extract_doc_ids(question)
    if len(doc_ids) >= 2 and is_compare_question(question):
        topic = _extract_topic(question)
        compare_result = await tool_executor.execute(
            "compare_documents",
            {"doc_id_a": doc_ids[0], "doc_id_b": doc_ids[1], "topic": topic},
        )
        left = compare_result.get(doc_ids[0], {}).get("sections", [])
        right = compare_result.get(doc_ids[1], {}).get("sections", [])
        sources = dedupe_sections(left + right)
        images = dedupe_images(compare_result.get("images", []))
        return {
            "answer": compose_compare_answer(question, sources, comparison=compare_result, all_images=images),
            "sources": sources,
            "images": images,
            "strategy_used": "parallel_rrf_fallback",
        }

    search_result = await tool_executor.execute(
        "search_sections",
        {"query": question, "doc_id": doc_ids[0] if doc_ids else "", "top_k": 5},
    )
    sources = search_result.get("sections", [])
    return {
        "answer": summarize_sources(sources),
        "sources": sources,
        "images": search_result.get("images", []),
        "strategy_used": "parallel_rrf_fallback",
    }
