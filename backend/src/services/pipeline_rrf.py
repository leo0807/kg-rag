from __future__ import annotations

import logging
from typing import Any

from .infra.cache import get_redis

logger = logging.getLogger(__name__)


def _resolve_alpha(params: dict) -> float:
    alpha = float(params.get("alpha", 0.5))
    if str(params.get("alpha_source", "fixed")) != "redis":
        return max(0.0, min(1.0, alpha))
    key = str(params.get("alpha_redis_key", "search:hybrid_alpha")).strip() or "search:hybrid_alpha"
    try:
        raw = get_redis().get(key)
        if raw is not None:
            alpha = float(raw)
    except Exception as exc:
        logger.warning("rrf alpha redis 读取失败: %s", exc)
    return max(0.0, min(1.0, alpha))


def run_rrf_fusion(params: dict, inputs: dict[str, Any]) -> dict:
    k = int(params.get("k", 60))
    all_lists = inputs.get("candidates") or []
    if not all_lists:
        return {"candidates": []}

    alpha = _resolve_alpha(params)
    weighted = len(all_lists) == 2 and str(params.get("alpha_source", "fixed")) == "redis"
    weights = [alpha, 1.0 - alpha] if weighted else [1.0] * len(all_lists)

    scores: dict[str, float] = {}
    id_to_sec: dict[str, dict] = {}
    for idx, lst in enumerate(all_lists):
        weight = weights[idx] if idx < len(weights) else 1.0
        for rank, sec in enumerate(lst, start=1):
            cid = sec.get("chunk_id", "")
            if cid:
                scores[cid] = scores.get(cid, 0.0) + weight / (k + rank)
                id_to_sec[cid] = sec

    return {
        "candidates": [id_to_sec[c] for c in sorted(scores, key=scores.get, reverse=True) if c in id_to_sec],
        "alpha": alpha,
    }
