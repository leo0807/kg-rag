"""
src/services/embedder.py
向量化入口 — 薄包装层，所有实现已迁移到 EmbeddingService。

保留此模块以维持对现有调用方的零改动兼容：
  from .embedder import embed_texts, embed_query, get_embedder
"""
import logging
from functools import lru_cache
from .embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化（向后兼容接口）。"""
    return get_embedding_service().embed_batch(texts)


def embed_query(text: str) -> list[float]:
    """单条查询向量化（向后兼容接口）。"""
    return get_embedding_service().embed(text)


@lru_cache(maxsize=200)
def get_cached_embedding(text: str) -> tuple[float, ...]:
    """高频查询 embedding 缓存，避免重复向量化。"""
    return tuple(get_embedding_service().embed(text.strip()))


def get_embedder():
    """
    向后兼容接口 — 直接返回 EmbeddingService 单例。
    原调用方若只使用 get_embedder() 来判断"模型是否加载"，
    可改为调用 get_embedding_service()。
    """
    return get_embedding_service()
