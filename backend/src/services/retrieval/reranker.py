"""
src/services/reranker.py
重排序服务，使用 BAAI/bge-reranker-v2-m3
"""
import logging
from pathlib import Path
from functools import lru_cache
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

RERANKER_PATH = Path(__file__).parent.parent.parent.parent / "models" / "bge-reranker-v2-m3"


def _get_device() -> str:
    """自动检测 CUDA，优先使用 GPU"""
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("检测到 CUDA，Reranker 模型使用 GPU 加速")
            return "cuda"
    except ImportError:
        pass
    return "cpu"


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    device = _get_device()
    logger.info("加载 Reranker 模型: %s (device=%s)", RERANKER_PATH, device)
    model = CrossEncoder(str(RERANKER_PATH), device=device)
    logger.info("Reranker 模型加载完成")
    return model


def _get_reranker() -> CrossEncoder:
    """向后兼容旧测试和调用方的私有入口。"""
    return get_reranker()


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

    model = _get_reranker()
    pairs = [
        # 1024 chars ≈ 512 tokens for Chinese text（比原来的 512 字符更充分）
        (query, f"{s.get('title', '')}\n{s.get('content', '')}"[:1024])
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
