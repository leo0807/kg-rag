"""
I2.1: Local model manager — list, load, unload, and benchmark locally-deployed AI models.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.deployment_models import LocalModel

logger = logging.getLogger(__name__)


# ── Backend probe helpers ────────────────────────────────────────────────────

class _Backend:
    """Minimal interface for querying a local inference backend."""
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def list_models(self) -> List[str]:
        raise NotImplementedError

    async def is_loaded(self, model_name: str) -> bool:
        return model_name in await self.list_models()


class OllamaBackend(_Backend):
    async def list_models(self) -> List[str]:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]

    async def load(self, model_name: str) -> None:
        async with httpx.AsyncClient(timeout=120.0) as c:
            await c.post(f"{self.base_url}/api/pull", json={"name": model_name})

    async def unload(self, model_name: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as c:
            await c.delete(f"{self.base_url}/api/delete", json={"name": model_name})


class VLLMBackend(_Backend):
    async def list_models(self) -> List[str]:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{self.base_url}/v1/models")
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]

    async def load(self, _: str) -> None:
        pass  # vLLM loads on startup; no runtime load API

    async def unload(self, _: str) -> None:
        pass


class TGIBackend(_Backend):
    """HuggingFace Text Generation Inference."""
    async def list_models(self) -> List[str]:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{self.base_url}/info")
            r.raise_for_status()
            info = r.json()
            return [info.get("model_id", "unknown")]

    async def load(self, _: str) -> None:
        pass

    async def unload(self, _: str) -> None:
        pass


_BACKEND_MAP: Dict[str, type] = {
    "ollama":   OllamaBackend,
    "vllm":     VLLMBackend,
    "tgi":      TGIBackend,
}


# ── Manager ──────────────────────────────────────────────────────────────────

class LocalModelManager:
    """Manages locally-deployed AI models across multiple backends."""

    def __init__(self) -> None:
        from ...core.config import settings
        self._ollama_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")

    def _get_backend(self, backend_name: str, url: Optional[str] = None) -> _Backend:
        cls = _BACKEND_MAP.get(backend_name.lower(), OllamaBackend)
        return cls(url or self._ollama_url)

    async def list_live_models(self, backend: str = "ollama") -> List[str]:
        """Return model names currently available in the backend."""
        try:
            return await self._get_backend(backend).list_models()
        except Exception as e:
            logger.warning("list_live_models(%s) failed: %s", backend, e)
            return []

    async def list_models(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """List registered models with live load-status annotation."""
        from sqlalchemy import select
        rows = (await db.execute(select(LocalModel).order_by(LocalModel.created_at))).scalars().all()
        live = await self.list_live_models()
        result = []
        for m in rows:
            d = {c.name: getattr(m, c.name) for c in m.__table__.columns}
            d["live_loaded"] = m.name in live
            result.append(d)
        return result

    async def load_model(self, db: AsyncSession, model_id: str) -> Dict[str, Any]:
        from sqlalchemy import select
        m = (await db.execute(select(LocalModel).where(LocalModel.id == model_id))).scalar_one_or_none()
        if not m:
            raise ValueError(f"模型 {model_id} 不存在")
        backend = self._get_backend(m.backend, m.model_path or None)
        start = time.monotonic()
        await backend.load(m.name)
        m.is_loaded = True
        m.load_time = round(time.monotonic() - start, 2)
        await db.commit()
        return {"status": "loaded", "load_time": m.load_time}

    async def unload_model(self, db: AsyncSession, model_id: str) -> Dict[str, Any]:
        from sqlalchemy import select
        m = (await db.execute(select(LocalModel).where(LocalModel.id == model_id))).scalar_one_or_none()
        if not m:
            raise ValueError(f"模型 {model_id} 不存在")
        backend = self._get_backend(m.backend, m.model_path or None)
        await backend.unload(m.name)
        m.is_loaded = False
        await db.commit()
        return {"status": "unloaded"}

    async def benchmark(self, model_name: str, backend: str = "ollama") -> Dict[str, Any]:
        """Simple benchmark: measure first-token latency and throughput."""
        from ...core.config import settings
        base = settings.LLM_API_URL.rstrip("/")
        prompt = "请用一句话描述液压系统的工作原理。"
        start = time.monotonic()
        tokens = 0
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(f"{base}/chat/completions", json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                    "stream": False,
                })
                r.raise_for_status()
                data = r.json()
                tokens = data.get("usage", {}).get("completion_tokens", 0)
        except Exception as e:
            return {"error": str(e)}
        elapsed = time.monotonic() - start
        return {
            "latency_s": round(elapsed, 3),
            "tokens": tokens,
            "tokens_per_second": round(tokens / elapsed, 1) if elapsed > 0 else 0,
        }

    async def get_model_status(self) -> Dict[str, Any]:
        """Return aggregate status: backend availability, loaded models list."""
        live = await self.list_live_models()
        return {
            "ollama_reachable": len(live) >= 0,
            "loaded_count": len(live),
            "models": live,
        }


local_model_manager = LocalModelManager()
