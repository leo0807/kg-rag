"""
H6.3 Webhook 管理 API
GET/POST/PUT/DELETE /api/admin/webhooks
POST /api/admin/webhooks/{id}/test
GET  /api/admin/webhooks/{id}/deliveries
"""
from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.integration_models import Webhook, WebhookDelivery
from ...db.models import User
from ...db.session import get_db
from ...services.integration.webhook_dispatcher import EVENT_TYPES
from ...services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(prefix="/api/admin/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    name: str
    url: str
    events: list[str]
    secret: str | None = None
    timeout_seconds: int = 30
    retry_policy: dict = {}


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None
    timeout_seconds: int | None = None


def _row(w: Webhook) -> dict:
    return {
        "id": w.id, "name": w.name, "url": w.url,
        "events": w.events, "is_active": w.is_active,
        "timeout_seconds": w.timeout_seconds,
        "success_count": w.success_count,
        "failure_count": w.failure_count,
        "last_triggered_at": w.last_triggered_at.isoformat() if w.last_triggered_at else None,
        "created_at": w.created_at.isoformat(),
        "has_secret": bool(w.secret),
    }


@router.get("")
async def list_webhooks(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    tid = get_tenant_id_optional(request)
    stmt = select(Webhook)
    if tid:
        stmt = stmt.where(Webhook.tenant_id == tid)
    rows = (await db.execute(stmt.order_by(Webhook.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("", status_code=201)
async def create_webhook(
    body: WebhookCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    invalid = [e for e in body.events if e not in EVENT_TYPES and e != "*"]
    if invalid:
        raise HTTPException(400, f"未知事件类型: {invalid}")

    tid = get_tenant_id_optional(request)
    wh = Webhook(
        id=str(uuid.uuid4()), tenant_id=tid,
        name=body.name, url=body.url, events=body.events,
        secret=body.secret or secrets.token_hex(32),
        timeout_seconds=body.timeout_seconds,
        retry_policy=body.retry_policy,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    resp = _row(wh)
    resp["secret"] = wh.secret  # 仅创建时返回明文 secret
    return resp


@router.put("/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    body: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    wh = (await db.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
    if not wh:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(wh, k, v)
    await db.commit()
    return _row(wh)


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    wh = (await db.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
    if not wh:
        raise HTTPException(404)
    await db.delete(wh)
    await db.commit()
    return {"ok": True}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    """发送一条测试事件。"""
    wh = (await db.execute(select(Webhook).where(Webhook.id == webhook_id))).scalar_one_or_none()
    if not wh:
        raise HTTPException(404)

    from ...services.integration.webhook_dispatcher import get_dispatcher
    dispatcher = get_dispatcher()
    if dispatcher:
        await dispatcher.dispatch("answer.created", {"test": True, "webhook_id": webhook_id})
        return {"ok": True, "message": "测试事件已发送"}
    return {"ok": False, "message": "Dispatcher 未初始化"}


@router.get("/{webhook_id}/deliveries")
async def list_deliveries(
    webhook_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    rows = (await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return [
        {
            "id": r.id, "event_type": r.event_type,
            "status": r.status, "response_status": r.response_status,
            "attempt_count": r.attempt_count,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/events")
async def list_event_types(_: User = Depends(get_admin_user)):
    return sorted(EVENT_TYPES)
