"""
I2.4: Admin API for local model management.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.deployment_models import LocalModel
from ...db.session import get_db
from ...db.models import User
from ...services.ai.local_model_manager import local_model_manager
from ...services.ai.local_router import local_model_router

router = APIRouter(prefix="/api/admin/local-models", tags=["admin-local-models"])


class ModelCreate(BaseModel):
    name: str
    version: str = "latest"
    backend: str = "ollama"        # ollama / vllm / tgi / llamacpp
    model_path: str = ""
    description: str = ""
    parameters_b: Optional[float] = None
    quantization: str = "fp16"
    context_length: Optional[int] = None
    gpu_memory_required_gb: Optional[float] = None
    use_cases: List[str] = []


class RouteUpdate(BaseModel):
    use_case: str   # qa / embedding / vision / reranker
    model_name: str
    backend: str = "ollama"
    api_url: str = ""


@router.get("")
async def list_models(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> List[Dict[str, Any]]:
    """List registered local models with live status."""
    return await local_model_manager.list_models(db)


@router.post("")
async def register_model(
    body: ModelCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Register a new local model in the registry."""
    m = LocalModel(
        id=str(uuid.uuid4()),
        name=body.name,
        version=body.version,
        backend=body.backend,
        model_path=body.model_path,
        description=body.description,
        parameters_b=body.parameters_b,
        quantization=body.quantization,
        context_length=body.context_length,
        gpu_memory_required_gb=body.gpu_memory_required_gb,
        use_cases=body.use_cases,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return {c.name: getattr(m, c.name) for c in m.__table__.columns}


@router.post("/{model_id}/load")
async def load_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    try:
        return await local_model_manager.load_model(db, model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载失败: {e}")


@router.post("/{model_id}/unload")
async def unload_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    try:
        return await local_model_manager.unload_model(db, model_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"卸载失败: {e}")


@router.post("/{model_id}/benchmark")
async def benchmark_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Run a quick benchmark on the specified model."""
    from sqlalchemy import select
    m = (await db.execute(select(LocalModel).where(LocalModel.id == model_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="模型不存在")
    result = await local_model_manager.benchmark(m.name, m.backend)
    # Persist metrics
    m.benchmark_metrics = result
    await db.commit()
    return result


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    from sqlalchemy import select
    m = (await db.execute(select(LocalModel).where(LocalModel.id == model_id))).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="模型不存在")
    await db.delete(m)
    await db.commit()
    return {"deleted": model_id}


@router.get("/status")
async def model_status(
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Real-time backend status."""
    return await local_model_manager.get_model_status()


@router.get("/routes")
async def get_routes(_: User = Depends(get_admin_user)) -> Dict[str, Any]:
    """Get current model routing config."""
    return local_model_router.to_dict()


@router.put("/routes")
async def update_route(
    body: RouteUpdate,
    _: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Update routing for a use-case."""
    from ...core.config import settings
    local_model_router.update_route(
        body.use_case,
        body.model_name,
        body.backend,
        body.api_url or settings.LLM_API_URL,
    )
    return {"updated": body.use_case, "model": body.model_name}
