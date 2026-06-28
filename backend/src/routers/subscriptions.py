"""
Knowledge subscription system.
Users subscribe to Document or Component updates → receive notifications.

POST /api/subscriptions          — subscribe
DELETE /api/subscriptions/{id}   — unsubscribe
GET  /api/subscriptions          — list my subscriptions
POST /api/subscriptions/notify   — internal: trigger notifications (called by ingest pipeline)
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Enum, Integer, String, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_db
from ..core.security import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

SubscriptionType = Literal["document", "component", "entity"]


class SubscriptionCreate(BaseModel):
    type: SubscriptionType
    target_id: str  # doc_id, component part_no, or entity name
    notify_via: list[str] = ["in_app"]  # "in_app" | "email"


class SubscriptionResponse(BaseModel):
    id: int
    type: str
    target_id: str
    notify_via: list[str]
    user_id: str


class NotifyRequest(BaseModel):
    type: SubscriptionType
    target_id: str
    change_summary: str
    doc_id: str | None = None


@router.post("/", response_model=SubscriptionResponse)
async def create_subscription(
    body: SubscriptionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """Subscribe to updates for a document, component, or entity."""
    from sqlalchemy import text
    result = await db.execute(
        text(
            """
            INSERT INTO knowledge_subscriptions (user_id, sub_type, target_id, notify_via, created_at)
            VALUES (:uid, :stype, :tid, :nvia, NOW())
            ON CONFLICT (user_id, sub_type, target_id) DO UPDATE
                SET notify_via = EXCLUDED.notify_via
            RETURNING id, user_id, sub_type, target_id, notify_via
            """
        ),
        {"uid": str(current_user.id), "stype": body.type,
         "tid": body.target_id, "nvia": ",".join(body.notify_via)},
    )
    await db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Subscription creation failed")
    return SubscriptionResponse(
        id=row[0], type=row[2], target_id=row[3],
        notify_via=row[4].split(","), user_id=row[1],
    )


@router.get("/")
async def list_subscriptions(
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    """List all active subscriptions for the current user."""
    from sqlalchemy import text
    result = await db.execute(
        text(
            """
            SELECT id, sub_type, target_id, notify_via, created_at
            FROM knowledge_subscriptions
            WHERE user_id = :uid
            ORDER BY created_at DESC
            """
        ),
        {"uid": str(current_user.id)},
    )
    rows = result.fetchall()
    return [
        {"id": r[0], "type": r[1], "target_id": r[2],
         "notify_via": r[3].split(","), "created_at": str(r[4])}
        for r in rows
    ]


@router.delete("/{sub_id}")
async def delete_subscription(
    sub_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user=Depends(get_current_user),
):
    from sqlalchemy import text
    result = await db.execute(
        text(
            "DELETE FROM knowledge_subscriptions WHERE id = :id AND user_id = :uid"
        ),
        {"id": sub_id, "uid": str(current_user.id)},
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"deleted": True}


@router.post("/notify")
async def trigger_notifications(
    request: NotifyRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Internal endpoint — called by ingest pipeline when a document is updated.
    Sends in-app notifications to all subscribers of the updated resource.
    """
    from sqlalchemy import text
    result = await db.execute(
        text(
            """
            SELECT ks.user_id, ks.notify_via
            FROM knowledge_subscriptions ks
            WHERE ks.sub_type = :stype AND ks.target_id = :tid
            """
        ),
        {"stype": request.type, "tid": request.target_id},
    )
    subscribers = result.fetchall()

    notified = 0
    for user_id, notify_via_str in subscribers:
        notify_channels = notify_via_str.split(",")
        if "in_app" in notify_channels:
            await db.execute(
                text(
                    """
                    INSERT INTO notifications (user_id, type, title, body, created_at, is_read)
                    VALUES (:uid, 'knowledge_update', :title, :body, NOW(), false)
                    """
                ),
                {
                    "uid": user_id,
                    "title": f"知识库更新: {request.target_id}",
                    "body": request.change_summary,
                },
            )
        notified += 1

    await db.commit()
    return {"notified_users": notified}
