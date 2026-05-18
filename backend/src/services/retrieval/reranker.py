"""
src/services/reranker.py
重排序服务，使用 BAAI/bge-reranker-v2-m3
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

import requests
from sentence_transformers import CrossEncoder

from ...core.config import settings
from ..runtime.model_settings import get_runtime_settings_namespace

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


def _load_local_model_max_length(model_path: str) -> int | None:
    """从本地 reranker 配置里读取 tokenizer / 模型上限。"""
    base = Path(model_path)
    for filename, key in (
        ("tokenizer_config.json", "model_max_length"),
        ("config.json", "max_position_embeddings"),
    ):
        try:
            data = json.loads((base / filename).read_text())
        except Exception:
            continue
        value = data.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


@lru_cache(maxsize=4)
def get_reranker(model_path: str | None = None) -> CrossEncoder:
    device = _get_device()
    path = model_path or str(RERANKER_PATH)
    logger.info("加载 Reranker 模型: %s (device=%s)", path, device)
    model = CrossEncoder(path, device=device, max_length=_load_local_model_max_length(path))
    logger.info("Reranker 模型加载完成")
    # 向 ModelManager 注册
    try:
        from ..model_manager import model_manager
        model_manager.register("reranker", model)
    except Exception:
        pass
    return model


def _get_reranker() -> CrossEncoder:
    """向后兼容旧测试和调用方的私有入口。
    优先级：运行时设置 > RERANKER_MODEL 环境变量 > 默认本地路径。
    """
    runtime_settings = get_runtime_settings_namespace()
    # 运行时覆盖 > settings（含 .env）> 默认路径
    model_path = (
        runtime_settings.RERANKER_MODEL
        or settings.RERANKER_MODEL
        or str(RERANKER_PATH)
    )
    return get_reranker(model_path)


class _ApiRerankerProvider:
    def __init__(self, api_url: str, api_key: str, model: str):
        self._url = api_url.rstrip("/")
        self._key = api_key
        self._model = model

    def predict(self, query: str, sections: list[dict]) -> list[float]:
        documents = [
            f"{section.get('title', '')}\n{section.get('content', '')}"[:2048]
            for section in sections
        ]
        response = requests.post(
            f"{self._url}/rerank",
            headers={
                "Authorization": f"Bearer {self._key}" if self._key else "",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "query": query,
                "documents": documents,
            },
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        items = body.get("results") or body.get("data") or []
        score_map: dict[int, float] = {}
        for item in items:
            index = item.get("index")
            score = item.get("relevance_score", item.get("score", 0.0))
            if isinstance(index, int):
                score_map[index] = float(score)
        return [score_map.get(idx, 0.0) for idx in range(len(sections))]


def _get_runtime_reranker_settings():
    runtime_settings = get_runtime_settings_namespace()
    mode = (runtime_settings.RERANKER_MODE or "local").lower()
    provider = (getattr(runtime_settings, "RERANKER_PROVIDER", "") or "").lower()
    enabled = getattr(runtime_settings, "RERANKER_ENABLED", settings.RERANKER_ENABLED)
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
    return runtime_settings, mode, provider, bool(enabled)


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

    runtime_settings, mode, _provider, enabled = _get_runtime_reranker_settings()
    if not enabled:
        return sections[:top_k]

    if mode == "api" and runtime_settings.RERANKER_API_URL:
        scores = _ApiRerankerProvider(
            api_url=runtime_settings.RERANKER_API_URL,
            api_key=runtime_settings.RERANKER_API_KEY,
            model=runtime_settings.RERANKER_MODEL or "reranker-v1",
        ).predict(query, sections)
    else:
        model = _get_reranker()
        pairs = [(query, f"{s.get('title', '')}\n{s.get('content', '')}") for s in sections]
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
