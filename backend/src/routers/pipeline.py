from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import PipelineConfig, User
from ..db.session import get_db
from ..core.pipeline_schema import NODE_TYPES, validate_pipeline

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────

class ConfigCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list[dict] = []
    edges: list[dict] = []
    params: dict[str, Any] = {}


class ConfigUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None
    params: dict[str, Any] | None = None


class ValidateBody(BaseModel):
    nodes: list[dict] = []
    edges: list[dict] = []


# ── Helpers ───────────────────────────────────────────────────────

def _to_dict(cfg: PipelineConfig) -> dict:
    return {
        "id":          cfg.id,
        "name":        cfg.name,
        "description": cfg.description,
        "is_default":  cfg.is_default,
        "nodes":       cfg.nodes,
        "edges":       cfg.edges,
        "params":      cfg.params,
        "created_at":  cfg.created_at.isoformat(),
        "updated_at":  cfg.updated_at.isoformat(),
    }


async def _get_owned(config_id: str, user_id: str, db: AsyncSession) -> PipelineConfig:
    result = await db.execute(
        select(PipelineConfig).where(
            PipelineConfig.id == config_id,
            PipelineConfig.user_id == user_id,
            PipelineConfig.is_active.is_(True),
        )
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    return cfg


# ── Routes ────────────────────────────────────────────────────────

@router.get("/api/pipeline/schema")
async def get_schema():
    """返回所有节点类型定义，供前端渲染节点面板。"""
    return {"node_types": NODE_TYPES}


@router.get("/api/pipeline/default")
async def get_default(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的默认链路配置，无默认时返回 null。"""
    result = await db.execute(
        select(PipelineConfig).where(
            PipelineConfig.user_id == current_user.id,
            PipelineConfig.is_default.is_(True),
            PipelineConfig.is_active.is_(True),
        )
    )
    cfg = result.scalar_one_or_none()
    return _to_dict(cfg) if cfg else None


@router.get("/api/pipeline")
async def list_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前用户所有链路配置（按更新时间降序）。"""
    result = await db.execute(
        select(PipelineConfig)
        .where(
            PipelineConfig.user_id == current_user.id,
            PipelineConfig.is_active.is_(True),
        )
        .order_by(PipelineConfig.updated_at.desc())
    )
    return [_to_dict(c) for c in result.scalars().all()]


@router.post("/api/pipeline", status_code=201)
async def create_config(
    body: ConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = PipelineConfig(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        nodes=body.nodes,
        edges=body.edges,
        params=body.params,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return _to_dict(cfg)


@router.put("/api/pipeline/{config_id}")
async def update_config(
    config_id: str,
    body: ConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_owned(config_id, current_user.id, db)
    if body.name is not None:        cfg.name        = body.name
    if body.description is not None: cfg.description = body.description
    if body.nodes is not None:       cfg.nodes       = body.nodes
    if body.edges is not None:       cfg.edges       = body.edges
    if body.params is not None:      cfg.params      = body.params
    cfg.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(cfg)
    return _to_dict(cfg)


@router.delete("/api/pipeline/{config_id}", status_code=204)
async def delete_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = await _get_owned(config_id, current_user.id, db)
    cfg.is_active = False
    if cfg.is_default:
        cfg.is_default = False
    await db.commit()


@router.post("/api/pipeline/{config_id}/set-default")
async def set_default(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 先清除所有默认标记
    await db.execute(
        update(PipelineConfig)
        .where(
            PipelineConfig.user_id == current_user.id,
            PipelineConfig.is_default.is_(True),
        )
        .values(is_default=False)
    )
    cfg = await _get_owned(config_id, current_user.id, db)
    cfg.is_default = True
    await db.commit()
    return {"ok": True}


@router.post("/api/pipeline/validate")
async def validate(
    body: ValidateBody,
    _: User = Depends(get_current_user),
):
    """验证链路合法性：拓扑、端口类型、孤立节点、环路检测。"""
    return validate_pipeline(body.nodes, body.edges)
