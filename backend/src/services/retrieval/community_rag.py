"""
GraphRAG Community Summaries (Microsoft GraphRAG style).

Workflow:
  1. Run Louvain community detection → Section nodes get community_id
  2. For each community, generate LLM summary stored in community_summaries table
  3. Global questions → retrieve community summaries
  4. Local questions → standard vector/graph retrieval

Route detection: questions with broad scope ("整体"/"所有"/"综述") → community mode.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

from ...core.config import settings
from ...core.database import get_driver
from ..ai.llm_service import get_llm_service

log = logging.getLogger(__name__)

_GLOBAL_PATTERNS = re.compile(
    r"整体|全部|所有|综述|概述|总结|overall|all|summary|overview|什么是.*系统", re.I
)


def is_global_question(question: str) -> bool:
    return bool(_GLOBAL_PATTERNS.search(question))


# ─── Community summary generation ────────────────────────────────────────────

async def generate_community_summary(community_id: int,
                                      sample_titles: list[str]) -> str:
    """Generate LLM summary for a community of sections."""
    svc = get_llm_service()
    titles_text = "\n".join(f"- {t}" for t in sample_titles[:20])
    prompt = (
        f"以下是航空工艺知识库中一个知识社区的相关章节主题（共 {len(sample_titles)} 个章节）：\n\n"
        f"{titles_text}\n\n"
        "请用 2-3 句话总结这个知识社区涵盖的主题和核心内容。"
    )
    try:
        return svc.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            timeout=30,
        )
    except Exception as exc:
        log.warning("Community summary generation failed: %s", exc)
        return f"Community covering {len(sample_titles)} sections in areas: {', '.join(sample_titles[:3])}"


async def build_community_summaries() -> dict[str, int]:
    """
    Build community summaries for all detected communities.
    Should be run after Louvain community detection.
    Returns {"communities_processed": N}.
    """
    from .graph_algorithms import get_communities  # type: ignore[import]

    communities = await asyncio.to_thread(get_communities, top_k=50)
    driver = get_driver()
    processed = 0

    for comm in communities:
        cid = comm["cid"]
        titles = comm.get("sample_titles", [])
        if not titles:
            continue

        summary = await generate_community_summary(cid, titles)

        # Store summary in Neo4j community node
        def _store(s=summary, c=cid, n=comm["member_count"]):
            with driver.session() as sess:
                sess.run(
                    """
                    MERGE (cs:CommunitySummary {community_id: $cid})
                    SET cs.summary = $summary,
                        cs.member_count = $count,
                        cs.updated_at = $ts
                    """,
                    cid=c, summary=s, count=n,
                    ts=datetime.utcnow().isoformat(),
                )
        await asyncio.to_thread(_store)
        processed += 1
        log.info("Community %s: summarized (%d sections)", cid, comm["member_count"])

    return {"communities_processed": processed}


# ─── Community-based retrieval ────────────────────────────────────────────────

async def retrieve_community_context(question: str,
                                      top_k: int = 5) -> list[dict[str, Any]]:
    """
    Retrieve relevant community summaries for global questions.
    Embeds question and finds semantically related communities.
    """
    driver = get_driver()

    def _get_summaries():
        with driver.session() as s:
            result = s.run(
                """
                MATCH (cs:CommunitySummary)
                RETURN cs.community_id AS community_id,
                       cs.summary AS summary,
                       cs.member_count AS member_count
                ORDER BY cs.member_count DESC
                LIMIT 50
                """
            )
            return [dict(r) for r in result]

    summaries = await asyncio.to_thread(_get_summaries)
    if not summaries:
        return []

    # Score by keyword overlap (lightweight before vector scoring)
    question_words = set(re.findall(r'[一-鿿]+|\w+', question.lower()))
    scored = []
    for s in summaries:
        text = (s.get("summary") or "").lower()
        summary_words = set(re.findall(r'[一-鿿]+|\w+', text))
        overlap = len(question_words & summary_words) / max(len(question_words), 1)
        scored.append({**s, "_score": overlap})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    top = scored[:top_k]

    return [
        {
            "chunk_id": f"community_{s['community_id']}",
            "title": f"知识社区 #{s['community_id']}（{s['member_count']} 个章节）",
            "content": s["summary"],
            "doc_id": "community_summary",
            "score": s["_score"],
            "source_type": "community_summary",
        }
        for s in top if s["_score"] > 0
    ]


async def get_all_community_summaries() -> list[dict[str, Any]]:
    """Return all stored community summaries for the frontend."""
    driver = get_driver()

    def _run():
        with driver.session() as s:
            result = s.run(
                """
                MATCH (cs:CommunitySummary)
                RETURN cs.community_id AS community_id,
                       cs.summary AS summary,
                       cs.member_count AS member_count,
                       cs.updated_at AS updated_at
                ORDER BY cs.member_count DESC
                """
            )
            return [dict(r) for r in result]

    return await asyncio.to_thread(_run)
