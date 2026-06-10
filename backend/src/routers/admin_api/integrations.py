"""
H1.3 集成管理 API
GET/POST/PUT/DELETE /api/admin/integrations
POST /api/admin/integrations/{id}/test
GET  /api/admin/integrations/{id}/logs
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.integration_models import Integration, IntegrationLog
from ...db.models import User
from ...db.session import get_db
from ...services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(prefix="/api/admin/integrations", tags=["integrations"])


class IntegrationCreate(BaseModel):
    name: str
    type: str
    endpoint: str | None = None
    auth_type: str | None = None
    auth_config: dict = {}
    settings: dict = {}


class IntegrationUpdate(BaseModel):
    name: str | None = None
    endpoint: str | None = None
    auth_type: str | None = None
    auth_config: dict | None = None
    settings: dict | None = None
    status: str | None = None


def _row(i: Integration) -> dict:
    return {
        "id": i.id, "name": i.name, "type": i.type,
        "endpoint": i.endpoint, "auth_type": i.auth_type,
        "status": i.status,
        "last_sync_at": i.last_sync_at.isoformat() if i.last_sync_at else None,
        "last_error": i.last_error, "settings": i.settings,
        "created_at": i.created_at.isoformat(),
    }


@router.get("")
async def list_integrations(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    tid = get_tenant_id_optional(request)
    stmt = select(Integration)
    if tid:
        stmt = stmt.where(Integration.tenant_id == tid)
    rows = (await db.execute(stmt.order_by(Integration.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_integration(
    body: IntegrationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    tid = get_tenant_id_optional(request)
    obj = Integration(
        id=str(uuid.uuid4()), tenant_id=tid,
        name=body.name, type=body.type,
        endpoint=body.endpoint, auth_type=body.auth_type,
        auth_config=body.auth_config, settings=body.settings,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return _row(obj)


@router.put("/{integration_id}")
async def update_integration(
    integration_id: str,
    body: IntegrationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    obj = (await db.execute(
        select(Integration).where(Integration.id == integration_id)
    )).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "集成不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.commit()
    return _row(obj)


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    obj = (await db.execute(
        select(Integration).where(Integration.id == integration_id)
    )).scalar_one_or_none()
    if not obj:
        raise HTTPException(404)
    await db.delete(obj)
    await db.commit()
    return {"ok": True}


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    obj = (await db.execute(
        select(Integration).where(Integration.id == integration_id)
    )).scalar_one_or_none()
    if not obj:
        raise HTTPException(404)

    from ...services.integration.base import build_provider
    provider = build_provider(obj)
    if provider is None:
        return {"ok": False, "error": f"未知集成类型: {obj.type}"}

    try:
        ok = await provider.test_connection()
        obj.status = "active" if ok else "error"
        obj.last_error = None if ok else "连接测试失败"
    except Exception as e:
        ok = False
        obj.status = "error"
        obj.last_error = str(e)[:500]

    await db.commit()
    return {"ok": ok, "status": obj.status, "error": obj.last_error}


@router.get("/{integration_id}/logs")
async def get_logs(
    integration_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    rows = (await db.execute(
        select(IntegrationLog)
        .where(IntegrationLog.integration_id == integration_id)
        .order_by(IntegrationLog.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return [
        {
            "id": r.id, "direction": r.direction, "action": r.action,
            "status": r.status, "duration_ms": r.duration_ms,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
