from __future__ import annotations

"""RRF 相关工具函数。"""


def rrf_fusion(ft_ids: list[str], vec_ids: list[str], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for rank, cid in enumerate(ft_ids, start=1):
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank)
    for rank, cid in enumerate(vec_ids, start=1):
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def rrf_scores(*rank_lists: list[str], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ids in rank_lists:
        for rank, cid in enumerate(ids, start=1):
            if not cid:
                continue
            scores[cid] = scores.get(cid, 0.0) + 1 / (k + rank)
    return scores
