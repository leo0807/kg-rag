import logging
from pathlib import Path
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from ..core.config import settings

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "bge-m3"

@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """单例模式加载模型，避免重复加载"""
    logger.info("加载 Embedding 模型: %s", MODEL_PATH)
    model = SentenceTransformer(str(MODEL_PATH), device="cpu")
    logger.info("Embedding 模型加载完成")
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.EMBEDDING_MODE == "api":
        return _embed_via_api(texts)
    return _embed_local(texts)

def _embed_via_api(texts: list[str]) -> list[list[float]]:
    """调用 OpenAI 兼容的 Embedding API"""
    import httpx
    res = httpx.post(
        f"{settings.EMBEDDING_API_URL}/embeddings",
        headers={"Authorization": f"Bearer {settings.EMBEDDING_API_KEY}"},
        json={"input": texts, "model": settings.EMBEDDING_MODEL},
        timeout=30,
    )
    data = res.json()
    return [item["embedding"] for item in data["data"]]

def _embed_local(texts: list[str]) -> list[list[float]]:
    """使用本地模型"""
    model = get_embedder()
    return model.encode(texts, normalize_embeddings=True).tolist()


def embed_query(text: str) -> list[float]:
    """单条查询向量化"""
    return embed_texts([text])[0]