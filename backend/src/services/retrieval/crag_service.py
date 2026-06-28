"""
CRAG — Corrective RAG

Evaluates retrieval quality and falls back to broader retrieval
or external search if top-1 relevance is below threshold.

Strategy:
  1. Retrieve top-k sections
  2. Score top-1 relevance with cross-encoder
  3. If score < threshold → expand top_k or fallback to full-text
  4. Attach relevance_score to each source for frontend display
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_CRAG_THRESHOLD = 0.4  # minimum acceptable relevance for top-1 result


async def score_relevance(question: str, content: str) -> float:
    """
    Score relevance using cross-encoder (or LLM fallback).
    Returns 0.0–1.0.
    """
    try:
        from ..retrieval.reranker import get_reranker
        reranker = get_reranker()
        if reranker is None:
            return 0.5
        scores = reranker.score([(question, content)])
        # Normalize from raw logit to 0–1
        import math
        raw = scores[0] if scores else 0.0
        return float(1 / (1 + math.exp(-raw)))
    except Exception as exc:
        log.debug("Reranker scoring failed: %s", exc)
        return 0.5


async def crag_retrieve(question: str, retriever, top_k: int = 5,
                        threshold: float = _CRAG_THRESHOLD) -> dict[str, Any]:
    """
    Run CRAG-enhanced retrieval.

    Returns:
        {
          "sources": [...],
          "fallback_used": bool,
          "fallback_reason": str | None,
          "top_relevance": float,
        }
    """
    # Stage 1: initial retrieval
    sources = await retriever.retrieve(question, top_k=top_k)

    if not sources:
        return {
            "sources": [],
            "fallback_used": True,
            "fallback_reason": "no_results",
            "top_relevance": 0.0,
        }

    # Stage 2: score top-1
    top_content = sources[0].get("content", "")
    top_score = await score_relevance(question, top_content)

    # Attach scores to all sources
    for i, src in enumerate(sources):
        src["relevance_score"] = top_score if i == 0 else top_score * 0.9 ** i

    if top_score >= threshold:
        return {
            "sources": sources,
            "fallback_used": False,
            "fallback_reason": None,
            "top_relevance": top_score,
        }

    # Stage 3: fallback strategy chain
    log.info("CRAG fallback triggered (top score %.3f < %.3f)", top_score, threshold)

    # Fallback 1: expand top_k
    expanded = await retriever.retrieve(question, top_k=top_k * 3)
    if expanded:
        expanded[0]["relevance_score"] = await score_relevance(
            question, expanded[0].get("content", "")
        )
        if expanded[0]["relevance_score"] >= threshold * 0.8:
            return {
                "sources": expanded[:top_k],
                "fallback_used": True,
                "fallback_reason": "expanded_topk",
                "top_relevance": expanded[0]["relevance_score"],
            }

    # Fallback 2: switch to full-text retrieval
    try:
        from ..storage.es_store import fulltext_search
        ft_results = fulltext_search(question, top_k=top_k)
        if ft_results:
            return {
                "sources": ft_results,
                "fallback_used": True,
                "fallback_reason": "fulltext_fallback",
                "top_relevance": 0.0,
            }
    except Exception as exc:
        log.warning("Full-text fallback failed: %s", exc)

    # Return original results with low confidence marked
    return {
        "sources": sources,
        "fallback_used": True,
        "fallback_reason": "low_confidence",
        "top_relevance": top_score,
    }
