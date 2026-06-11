"""
I2.3: Local model router — selects the right locally-deployed model for each task.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ...core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelSpec:
    name: str
    backend: str       # ollama / vllm / tgi
    api_url: str
    use_case: str


# Default routing table (overridable via env-vars or DB config)
_DEFAULT_ROUTES: dict[str, ModelSpec] = {
    "qa": ModelSpec(
        name=settings.LLM_MODEL,
        backend="ollama",
        api_url=settings.LLM_API_URL,
        use_case="qa",
    ),
    "embedding": ModelSpec(
        name=settings.EMBEDDING_MODEL,
        backend="local",
        api_url=settings.EMBEDDING_API_URL or settings.LLM_API_URL,
        use_case="embedding",
    ),
    "vision": ModelSpec(
        name=getattr(settings, "LOCAL_VLM_PATH", "models/qwen2-vl"),
        backend="ollama",
        api_url=settings.LLM_API_URL,
        use_case="vision",
    ),
    "reranker": ModelSpec(
        name=settings.RERANKER_MODEL,
        backend="local",
        api_url=settings.RERANKER_API_URL or settings.LLM_API_URL,
        use_case="reranker",
    ),
}


class LocalModelRouter:
    """Routes AI requests to the appropriate local model."""

    def __init__(self, overrides: Optional[dict[str, ModelSpec]] = None) -> None:
        self._routes: dict[str, ModelSpec] = {**_DEFAULT_ROUTES, **(overrides or {})}

    def get_model(self, use_case: str) -> ModelSpec:
        spec = self._routes.get(use_case)
        if spec is None:
            logger.warning("No local model configured for use_case=%s, falling back to qa", use_case)
            spec = self._routes["qa"]
        return spec

    def get_qa_model(self) -> str:
        return self.get_model("qa").name

    def get_embedding_model(self) -> str:
        return self.get_model("embedding").name

    def get_vision_model(self) -> str:
        return self.get_model("vision").name

    def get_reranker(self) -> str:
        return self.get_model("reranker").name

    def to_dict(self) -> dict:
        return {k: {"name": v.name, "backend": v.backend, "api_url": v.api_url}
                for k, v in self._routes.items()}

    def update_route(self, use_case: str, model_name: str, backend: str, api_url: str) -> None:
        self._routes[use_case] = ModelSpec(
            name=model_name, backend=backend, api_url=api_url, use_case=use_case
        )
        logger.info("路由已更新: %s → %s (%s)", use_case, model_name, backend)


local_model_router = LocalModelRouter()
