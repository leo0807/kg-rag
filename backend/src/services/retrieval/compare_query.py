from __future__ import annotations

import asyncio
import logging

from ...services.answer_guard import validate_answer
from ...services.ai.llm import clean_llm_response
from ...routers.query.core import do_retrieval
from ...services.agent.agent_helpers import (
    build_compare_topic,
    dedupe_images,
    dedupe_sections,
    extract_compare_doc_ids,
)
from .compare_images import (
    attach_figure_labels,
    search_images_for_doc,
    search_images_for_pages,
    search_images_for_sections,
)
from .compare_summary import summarize_compare_answer

logger = logging.getLogger(__name__)


async def run_compare_query(
    driver,
    question: str,
    strategy: str,
    top_k: int,
    use_hyde: bool = False,
    hyde_alpha: float = 0.5,
) -> dict | None:
    doc_ids = extract_compare_doc_ids(question)
    if len(doc_ids) < 2:
        return None

    compare_topic = build_compare_topic(question)

    async def _run_for_doc(doc_id: str) -> tuple[list[dict], dict[str, float], list[str]]:
        return await asyncio.to_thread(
            do_retrieval,
            driver,
            compare_topic,
            strategy,
            top_k,
            use_hyde,
            hyde_alpha,
            doc_id,
            True,
        )

    try:
        res_a, res_b = await asyncio.gather(
            _run_for_doc(doc_ids[0]),
            _run_for_doc(doc_ids[1]),
        )
    except Exception as exc:
        logger.warning("比较题专用检索失败，降级到通用检索: %s", exc)
        return None

    sections_a, ft_scores_a, expansion_a = res_a
    sections_b, ft_scores_b, expansion_b = res_b
    sections = dedupe_sections([*sections_a, *sections_b])
    section_ids_a = [s.get("chunk_id", "") for s in sections_a if s.get("chunk_id")]
    section_ids_b = [s.get("chunk_id", "") for s in sections_b if s.get("chunk_id")]
    page_nums_a = [int(s.get("page_idx")) + 1 for s in sections_a if s.get("page_idx") is not None]
    page_nums_b = [int(s.get("page_idx")) + 1 for s in sections_b if s.get("page_idx") is not None]
    images_a = await search_images_for_doc(driver, doc_ids[0], compare_topic)
    images_b = await search_images_for_doc(driver, doc_ids[1], compare_topic)
    section_images_a = await search_images_for_sections(driver, section_ids_a)
    section_images_b = await search_images_for_sections(driver, section_ids_b)
    page_images_a = await search_images_for_pages(driver, doc_ids[0], page_nums_a)
    page_images_b = await search_images_for_pages(driver, doc_ids[1], page_nums_b)
    images = dedupe_images(
        [*images_a, *images_b, *section_images_a, *section_images_b, *page_images_a, *page_images_b]
    )
    images = attach_figure_labels(images, sections)
    answer = await summarize_compare_answer(question, sections, images)
    answer = validate_answer(clean_llm_response(answer), sections, question)
    ft_score_map = {**ft_scores_a, **ft_scores_b}
    return {
        "answer": answer,
        "sections": sections,
        "images": images,
        "ft_score_map": ft_score_map,
        "comparison_hint": f"请对比{doc_ids[0]}和{doc_ids[1]}关于{compare_topic}的异同",
        "expansion_info": list(dict.fromkeys([*(expansion_a or []), *(expansion_b or [])])),
        "doc_ids": doc_ids[:2],
    }
