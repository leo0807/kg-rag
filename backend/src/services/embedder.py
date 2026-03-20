import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_MODEL_NAME = "BAAI/bge-m3"
_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("加载 embedding 模型 %s ...", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("模型加载完成")
    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()
