"""
backend/src/services/embedding_service.py
统一 Embedding 服务层

通过环境变量控制提供方，屏蔽所有模型加载和 HTTP 细节：

  EMBEDDING_MODE=local
    → 本地 BAAI/bge-m3（维度 1024，支持 GPU 加速，保持现有行为不变）

  EMBEDDING_MODE=api  + EMBEDDING_PROVIDER=qwen
    → 通义文本向量 (DashScope OpenAI 兼容端点)
    → 默认模型 text-embedding-v3（维度 1024）

  EMBEDDING_MODE=api  + EMBEDDING_PROVIDER=""（或任意其他值）
    → 通用 OpenAI 兼容 Embedding API（EMBEDDING_API_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL）

主要接口：
  svc.embed(text)         → list[float]       # 单条
  svc.embed_batch(texts)  → list[list[float]] # 批量
  svc.dim                 → int               # 向量维度
  svc.model_name          → str               # 当前模型标识
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..runtime.model_settings import get_runtime_settings_namespace

logger = logging.getLogger(__name__)


def _resolve_device(device: str) -> str:
    """将 device 设置（auto/cpu/cuda/mps）解析为实际可用的 device 字符串。"""
    if device != "auto":
        return device
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


# ─────────────────────────────────────────────────────────────────────────────
# 底层提供方
# ─────────────────────────────────────────────────────────────────────────────

class _LocalBGEProvider:
    """本地 BAAI/bge-m3（SentenceTransformer），与现有 embedder.py 保持完全一致。"""

    _DIM = 1024

    def __init__(self, model_path: str, device: str = "auto"):
        self._model_path = model_path
        self._device = device
        self._model = None   # lazy load

    @property
    def model_name(self) -> str:
        return str(self._model_path)

    @property
    def dim(self) -> int:
        return self._DIM

    def _load(self):
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer
        device = _resolve_device(self._device)
        logger.info("加载本地 Embedding 模型: %s (device=%s)", self._model_path, device)
        self._model = SentenceTransformer(str(self._model_path), device=device)
        logger.info("Embedding 模型加载完成")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load()
        return self._model.encode(texts, normalize_embeddings=True).tolist()


class _OpenAICompatEmbeddingProvider:
    """通用 OpenAI 兼容 Embedding API（含通义千问 DashScope 兼容端点）。"""

    def __init__(self, api_url: str, api_key: str, model: str, dim: int = 1024, batch_size: int = 25):
        self._url        = api_url.rstrip("/")
        self._key        = api_key
        self._model      = model
        self._dim        = dim
        self._batch_size = batch_size

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dim(self) -> int:
        return self._dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import requests
        results: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            resp  = requests.post(
                f"{self._url}/embeddings",
                headers={"Authorization": f"Bearer {self._key}",
                         "Content-Type":  "application/json"},
                json={"model": self._model, "input": batch},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            batch_vecs = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
            results.extend(batch_vecs)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# EmbeddingService — 统一入口
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingService:
    """
    统一 Embedding 服务。

    通过以下方法调用：
      .embed(text)         → list[float]
      .embed_batch(texts)  → list[list[float]]
      .dim                 → int
      .model_name          → str
    """

    def __init__(self, runtime_settings=None):
        self._settings = runtime_settings or get_runtime_settings_namespace()
        self._provider = self._build_provider(self._settings)

    @staticmethod
    def _build_provider(s):
        mode     = (s.EMBEDDING_MODE     or "local").lower()
        provider = (s.EMBEDDING_PROVIDER or "").lower()
        if provider in {"openai", "openai_compatible", "openai-compatible", "generic"}:
            provider = ""

        if mode == "local":
            model_path = Path(s.EMBEDDING_MODEL) if s.EMBEDDING_MODEL else \
                         Path(__file__).parent.parent.parent.parent / "models" / "bge-m3"
            device = getattr(s, "EMBEDDING_DEVICE", "auto")
            logger.info("EmbeddingService → 本地 BGE-M3 path=%s device=%s", model_path, device)
            return _LocalBGEProvider(str(model_path), device=device)

        batch_size = getattr(s, "REMOTE_EMBEDDING_BATCH_SIZE", 25)

        # API 模式
        if provider == "qwen":
            model = s.EMBEDDING_MODEL or s.EMBEDDING_QWEN_MODEL or "text-embedding-v3"
            dim   = s.EMBEDDING_QWEN_DIM   or 1024
            logger.info("EmbeddingService → 通义文本向量 model=%s dim=%d batch_size=%d", model, dim, batch_size)
            return _OpenAICompatEmbeddingProvider(
                api_url    = "https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key    = s.EMBEDDING_API_KEY or s.DASHSCOPE_API_KEY,
                model      = model,
                dim        = dim,
                batch_size = batch_size,
            )

        # 通用 OpenAI 兼容（向后兼容旧 EMBEDDING_API_URL/KEY/MODEL 配置）
        model = s.EMBEDDING_MODEL or "text-embedding-ada-002"
        logger.info("EmbeddingService → 通用 API url=%s model=%s batch_size=%d", s.EMBEDDING_API_URL, model, batch_size)
        return _OpenAICompatEmbeddingProvider(
            api_url    = s.EMBEDDING_API_URL,
            api_key    = s.EMBEDDING_API_KEY,
            model      = model,
            batch_size = batch_size,
        )

    @staticmethod
    def _build_api_fallback_provider(s):
        if s.DASHSCOPE_API_KEY:
            model = s.EMBEDDING_MODEL or s.EMBEDDING_QWEN_MODEL or "text-embedding-v3"
            dim   = s.EMBEDDING_QWEN_DIM or 1024
            logger.warning("本地 Embedding 不可用，自动回落到通义文本向量 model=%s", model)
            return _OpenAICompatEmbeddingProvider(
                api_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=s.EMBEDDING_API_KEY or s.DASHSCOPE_API_KEY,
                model=model,
                dim=dim,
            )

        if s.EMBEDDING_API_URL and s.EMBEDDING_API_KEY:
            model = s.EMBEDDING_MODEL or "text-embedding-ada-002"
            logger.warning("本地 Embedding 不可用，自动回落到兼容 Embedding API model=%s", model)
            return _OpenAICompatEmbeddingProvider(
                api_url=s.EMBEDDING_API_URL,
                api_key=s.EMBEDDING_API_KEY,
                model=model,
            )

        return None

    # ── 公共接口 ────────────────────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def dim(self) -> int:
        return self._provider.dim

    def embed(self, text: str) -> list[float]:
        """单条文本向量化。"""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化。"""
        if not texts:
            return []
        try:
            return self._provider.embed_batch(texts)
        except Exception as e:
            if isinstance(self._provider, _LocalBGEProvider):
                fallback_provider = self._build_api_fallback_provider(self._settings)
                if fallback_provider is not None:
                    logger.warning("EmbeddingService 本地模式失败，切换到 API 回退: %s", e)
                    self._provider = fallback_provider
                    return self._provider.embed_batch(texts)
            logger.error("EmbeddingService.embed_batch 失败 (texts=%d): %s", len(texts), e)
            raise


# ─────────────────────────────────────────────────────────────────────────────
# 模块级单例
# ─────────────────────────────────────────────────────────────────────────────

_services: dict[tuple, EmbeddingService] = {}


def _service_key(runtime_settings) -> tuple:
    return (
        runtime_settings.EMBEDDING_MODE,
        runtime_settings.EMBEDDING_PROVIDER,
        runtime_settings.EMBEDDING_MODEL,
        runtime_settings.EMBEDDING_API_URL,
        runtime_settings.EMBEDDING_API_KEY,
        getattr(runtime_settings, "EMBEDDING_DEVICE", "auto"),
        getattr(runtime_settings, "REMOTE_EMBEDDING_BATCH_SIZE", 25),
    )


def get_embedding_service() -> EmbeddingService:
    """按当前运行时配置返回 EmbeddingService。"""
    runtime_settings = get_runtime_settings_namespace()
    key = _service_key(runtime_settings)
    if key not in _services:
        _services[key] = EmbeddingService(runtime_settings)
    return _services[key]
