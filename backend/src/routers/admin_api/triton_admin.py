"""
Triton Inference Server admin endpoints.

GET  /api/admin/triton/status     — 检查 Triton 存活状态
GET  /api/admin/triton/models     — 列举已加载模型及配置
POST /api/admin/triton/embed-test — 触发 BGE-M3 端到端测试
POST /api/admin/triton/rerank-test— 触发 bge-reranker 端到端测试
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...auth.deps import get_admin_user
from ...db.models import User
from ...services.ai.triton_client import (
    TritonUnavailable,
    embed_bge_m3,
    get_triton_client,
    rerank_bge_reranker,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/triton", tags=["admin-triton"])


@router.get("/status")
async def triton_status(_: User = Depends(get_admin_user)) -> dict[str, Any]:
    client = get_triton_client()
    live = client.is_live()
    return {"triton_url": client.url, "live": live,
            "status": "ok" if live else "unreachable"}


@router.get("/models")
async def triton_models(_: User = Depends(get_admin_user)) -> dict[str, Any]:
    """List models registered on Triton and their ready status."""
    try:
        import tritonclient.grpc as tc  # type: ignore
        conn = tc.InferenceServerClient(url=get_triton_client().url)
        repo = conn.get_model_repository_index()
        models = [{"name": m.name, "version": m.version, "state": m.state}
                  for m in repo.models]
        return {"count": len(models), "models": models}
    except ImportError:
        raise HTTPException(status_code=503, detail="tritonclient not installed")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


class EmbedTestBody(BaseModel):
    texts: list[str] = ["测试文本", "Triton embedding test"]


@router.post("/embed-test")
async def triton_embed_test(
    body: EmbedTestBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Send test texts to BGE-M3 on Triton; return embedding shape."""
    try:
        vecs = await embed_bge_m3(body.texts)
        return {"ok": True, "input_count": len(body.texts),
                "embedding_shape": list(vecs.shape)}
    except TritonUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class RerankTestBody(BaseModel):
    pairs: list[list[str]] = [["查询文本", "候选文本示例"]]


@router.post("/rerank-test")
async def triton_rerank_test(
    body: RerankTestBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Send test pairs to bge-reranker on Triton; return scores."""
    try:
        pairs = [(p[0], p[1]) for p in body.pairs if len(p) >= 2]
        scores = await rerank_bge_reranker(pairs)
        return {"ok": True, "pairs": len(pairs), "scores": scores}
    except TritonUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
