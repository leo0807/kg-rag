import logging
from pathlib import Path
from functools import lru_cache
from sentence_transformers import SentenceTransformer

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
    """批量文本向量化"""
    model = get_embedder()
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,  # 归一化，方便余弦相似度计算
    )
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """单条查询向量化"""
    return embed_texts([text])[0]