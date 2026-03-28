"""
src/services/reranker.py
重排序服务，使用 BAAI/bge-reranker-v2-m3
"""
import logging
from pathlib import Path
from functools import lru_cache
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

RERANKER_PATH = Path(__file__).parent.parent.parent / "models" / "bge-reranker-v2-m3"


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    logger.info("加载 Reranker 模型: %s", RERANKER_PATH)
    model = CrossEncoder(str(RERANKER_PATH), device="cpu")
    logger.info("Reranker 模型加载完成")
    return model


def rerank(
    query:    str,
    sections: list[dict],
    top_k:    int = 5,
) -> list[dict]:
    """
    对检索结果重排序
    sections: [{"chunk_id": ..., "title": ..., "content": ..., ...}]
    返回按相关度重排后的 top_k 个结果
    """
    if not sections:
        return []

    model  = get_reranker()
    pairs  = [
        (query, f"{s['title']}\n{s.get('content', '')[:512]}")
        for s in sections
    ]
    scores = model.predict(pairs)

    ranked = sorted(
        zip(sections, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    result = []
    for section, score in ranked[:top_k]:
        result.append({**section, "rerank_score": float(score)})
    return result