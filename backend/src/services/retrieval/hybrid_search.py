"""
Hybrid search: score = α × BM25 + (1-α) × cosine_similarity

α is read from Redis at query time (set via admin API), defaulting to 0.5.
Falls back to pure BM25 if vector query fails.

Usage:
    from .hybrid_search import hybrid_search
    results = hybrid_search(query="液压管路力矩", top_k=10, alpha=0.5)

Admin API to update α dynamically:
    redis-cli SET hybrid_search_alpha 0.7
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

log = logging.getLogger(__name__)

INDEX_NAME      = "cps_sections"
DEFAULT_ALPHA   = float(os.getenv("HYBRID_SEARCH_ALPHA", "0.5"))
REDIS_ALPHA_KEY = "hybrid_search_alpha"


def _get_alpha() -> float:
    """Read α from Redis; fall back to env default."""
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                           decode_responses=True)
        val = r.get(REDIS_ALPHA_KEY)
        if val is not None:
            return max(0.0, min(1.0, float(val)))
    except Exception:
        pass
    return DEFAULT_ALPHA


def _bm25_search(es, query: str, top_k: int) -> list[dict]:
    resp = es.search(
        index=INDEX_NAME,
        body={
            "size": top_k,
            "query": {
                "multi_match": {
                    "query":  query,
                    "fields": ["title^2", "content"],
                    "type":   "best_fields",
                }
            },
            "_source": ["chunk_id", "doc_id", "number", "title", "content"],
        },
    )
    hits = resp["hits"]["hits"]
    max_score = hits[0]["_score"] if hits else 1.0
    return [
        {
            **h["_source"],
            "bm25_score": h["_score"] / max(max_score, 1e-9),
        }
        for h in hits
    ]


def _knn_search(es, query_vec: list[float], top_k: int) -> list[dict]:
    resp = es.search(
        index=INDEX_NAME,
        body={
            "size": top_k,
            "knn": {
                "field":         "embedding",
                "query_vector":  query_vec,
                "k":             top_k,
                "num_candidates": top_k * 5,
            },
            "_source": ["chunk_id", "doc_id", "number", "title", "content"],
        },
    )
    hits = resp["hits"]["hits"]
    max_score = hits[0]["_score"] if hits else 1.0
    return [
        {
            **h["_source"],
            "cosine_score": h["_score"] / max(max_score, 1e-9),
        }
        for h in hits
    ]


def hybrid_search(
    query: str,
    top_k: int = 10,
    alpha: float | None = None,
) -> list[dict[str, Any]]:
    """
    Return up to top_k results ranked by:
        final_score = α × bm25_norm + (1-α) × cosine_norm

    Args:
        query:  User question or search term
        top_k:  Number of results to return
        alpha:  Weight for BM25 (0=pure vector, 1=pure BM25, None=read from Redis)

    Returns:
        List of dicts with chunk_id, doc_id, title, content, score, bm25_score, cosine_score
    """
    if alpha is None:
        alpha = _get_alpha()
    alpha = max(0.0, min(1.0, alpha))

    from ..storage.es_store import get_es
    es = get_es()

    # Always run BM25
    bm25_results = _bm25_search(es, query, top_k * 2)
    bm25_map: dict[str, dict] = {r["chunk_id"]: r for r in bm25_results}

    knn_map: dict[str, dict] = {}
    if alpha < 1.0:
        try:
            from .embedder import embed_query
            query_vec = embed_query(query)
            knn_results = _knn_search(es, query_vec, top_k * 2)
            knn_map = {r["chunk_id"]: r for r in knn_results}
        except Exception as exc:
            log.warning("KNN search failed, using BM25 only: %s", exc)
            alpha = 1.0

    # Merge scores over union of candidate chunk_ids
    all_ids = set(bm25_map) | set(knn_map)
    merged: list[dict] = []
    for cid in all_ids:
        bm25_s = bm25_map.get(cid, {}).get("bm25_score", 0.0)
        cos_s  = knn_map.get(cid, {}).get("cosine_score", 0.0)
        base   = bm25_map.get(cid) or knn_map.get(cid, {})
        merged.append({
            "chunk_id":     cid,
            "doc_id":       base.get("doc_id", ""),
            "number":       base.get("number", ""),
            "title":        base.get("title", ""),
            "content":      base.get("content", ""),
            "bm25_score":   round(bm25_s, 4),
            "cosine_score": round(cos_s, 4),
            "score":        round(alpha * bm25_s + (1 - alpha) * cos_s, 4),
            "alpha":        alpha,
        })

    merged.sort(key=lambda x: -x["score"])
    return merged[:top_k]
