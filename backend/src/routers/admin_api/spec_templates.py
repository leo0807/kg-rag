"""
GET    /api/admin/spec-templates         — 模板列表
POST   /api/admin/spec-templates         — 新建模板
PUT    /api/admin/spec-templates/{id}    — 更新模板
DELETE /api/admin/spec-templates/{id}    — 删除模板
POST   /api/admin/spec-templates/auto-extract — 从文档自动提取模板
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.gen_models import SpecTemplate
from ...db.session import get_db
from ...services.generation.structure_analyzer import (
    extract_template_from_docs,
    get_default_templates,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/spec-templates", tags=["admin-generation"])


class TemplateCreate(BaseModel):
    template_id:   str
    name:          str
    applicable_to: list[str] = []
    structure:     dict      = {}
    sample_doc_ids:list[str] = []


class TemplateUpdate(BaseModel):
    name:          str | None = None
    applicable_to: list[str] | None = None
    structure:     dict | None = None
    sample_doc_ids:list[str] | None = None


class AutoExtractRequest(BaseModel):
    doc_ids:       list[str]
    template_id:   str
    name:          str
    applicable_to: list[str] = []


def _to_dict(t: SpecTemplate) -> dict:
    return {
        "id":            t.id,
        "template_id":   t.template_id,
        "name":          t.name,
        "applicable_to": t.applicable_to,
        "structure":     t.structure,
        "sample_doc_ids":t.sample_doc_ids,
        "created_at":    t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    result = await db.execute(select(SpecTemplate).order_by(SpecTemplate.created_at))
    items = [_to_dict(t) for t in result.scalars().all()]
    return {"items": items, "total": len(items)}


@router.post("")
async def create_template(
    body: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    existing = await db.execute(
        select(SpecTemplate).where(SpecTemplate.template_id == body.template_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"template_id '{body.template_id}' already exists")

    tpl = SpecTemplate(
        template_id=body.template_id,
        name=body.name,
        applicable_to=body.applicable_to,
        structure=body.structure,
        sample_doc_ids=body.sample_doc_ids,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return _to_dict(tpl)


@router.put("/{tpl_id}")
async def update_template(
    tpl_id: str,
    body: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    result = await db.execute(select(SpecTemplate).where(SpecTemplate.id == tpl_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="template not found")

    if body.name          is not None: tpl.name           = body.name
    if body.applicable_to is not None: tpl.applicable_to  = body.applicable_to
    if body.structure     is not None: tpl.structure       = body.structure
    if body.sample_doc_ids is not None: tpl.sample_doc_ids = body.sample_doc_ids

    await db.commit()
    await db.refresh(tpl)
    return _to_dict(tpl)


@router.delete("/{tpl_id}", status_code=204)
async def delete_template(
    tpl_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    result = await db.execute(select(SpecTemplate).where(SpecTemplate.id == tpl_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="template not found")
    await db.delete(tpl)
    await db.commit()


@router.post("/auto-extract")
async def auto_extract(
    body: AutoExtractRequest,
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    """从指定文档列表中自动提取结构模板并入库。"""
    existing = await db.execute(
        select(SpecTemplate).where(SpecTemplate.template_id == body.template_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"template_id '{body.template_id}' already exists")

    import asyncio
    tpl_data = await asyncio.to_thread(
        extract_template_from_docs,
        driver, body.doc_ids, body.template_id, body.name, body.applicable_to,
    )

    tpl = SpecTemplate(
        template_id=tpl_data["template_id"],
        name=tpl_data["name"],
        applicable_to=tpl_data["applicable_to"],
        structure=tpl_data["structure"],
        sample_doc_ids=tpl_data.get("sample_doc_ids", []),
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return _to_dict(tpl)


@router.post("/seed-defaults")
async def seed_default_templates(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    """将内置默认模板写入数据库（已存在则跳过）。"""
    inserted = []
    for td in get_default_templates():
        existing = await db.execute(
            select(SpecTemplate).where(SpecTemplate.template_id == td["template_id"])
        )
        if existing.scalar_one_or_none():
            continue
        tpl = SpecTemplate(
            template_id=td["template_id"],
            name=td["name"],
            applicable_to=td["applicable_to"],
            structure=td["structure"],
            sample_doc_ids=td.get("sample_doc_ids", []),
        )
        db.add(tpl)
        inserted.append(td["template_id"])
    await db.commit()
    return {"inserted": inserted}
