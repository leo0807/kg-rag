"""
会话分享 API — 生成只读分享链接 / 查看分享内容 / 撤销分享
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote

from ..auth.deps import get_current_user, get_optional_user
from ..db.models import Conversation, User
from ..db.session import get_db
from ..db.ux_models import SharedConversation
from ..services.conversation.exporter import export_json, export_markdown, export_docx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["sharing"])
public_router = APIRouter(prefix="/api/shared", tags=["sharing"])


class ShareCreate(BaseModel):
    expires_days: int | None = None   # None = never
    is_public:    bool        = True


# ── Create / revoke share ─────────────────────────────────────────────────────

@router.post("/{conv_id}/share")
async def create_share(
    conv_id: str, req: ShareCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")

    # reuse existing share if any
    existing = await db.execute(
        select(SharedConversation).where(SharedConversation.conversation_id == conv_id)
    )
    shared = existing.scalar_one_or_none()
    expires = (
        datetime.now() + timedelta(days=req.expires_days)
        if req.expires_days else None
    )
    if shared:
        shared.expires_at = expires
        shared.is_public  = req.is_public
    else:
        shared = SharedConversation(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            created_by=user.id,
            expires_at=expires,
            is_public=req.is_public,
        )
        db.add(shared)
    await db.commit()
    await db.refresh(shared)
    return {
        "token":      shared.share_token,
        "expires_at": shared.expires_at.isoformat() if shared.expires_at else None,
        "is_public":  shared.is_public,
    }


@router.delete("/{conv_id}/share")
async def revoke_share(
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SharedConversation).where(SharedConversation.conversation_id == conv_id)
    )
    shared = result.scalar_one_or_none()
    if not shared:
        raise HTTPException(404, "分享链接不存在")
    # only creator can revoke
    if shared.created_by != user.id:
        raise HTTPException(403, "无权限")
    await db.delete(shared)
    await db.commit()
    return {"status": "revoked"}


# ── Export ─────────────────────────────────────────────────────────────────────

@router.post("/{conv_id}/export")
async def export_conversation(
    conv_id: str,
    fmt: str = Query("markdown", pattern="^(markdown|json|docx)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")

    messages = json.loads(conv.messages) if conv.messages else []
    meta = {"strategy": getattr(conv, "strategy", "")}
    safe_name = quote(conv.title or "conversation", safe="")

    if fmt == "json":
        content = export_json(conv.title, messages, meta)
        return Response(content, media_type="application/json",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.json"})
    if fmt == "docx":
        content = export_docx(conv.title, messages, meta)
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.docx"},
        )
    content = export_markdown(conv.title, messages, meta)
    return Response(content, media_type="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.md"})


# ── Public view ────────────────────────────────────────────────────────────────

@public_router.get("/{token}")
async def view_shared(
    token: str,
    db: AsyncSession = Depends(get_db),
    _user: User | None = Depends(get_optional_user),
):
    result = await db.execute(
        select(SharedConversation).where(SharedConversation.share_token == token)
    )
    shared = result.scalar_one_or_none()
    if not shared:
        raise HTTPException(404, "分享链接不存在或已失效")
    if shared.expires_at and shared.expires_at < datetime.now():
        raise HTTPException(410, "分享链接已过期")

    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == shared.conversation_id)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "对话不存在")

    shared.view_count += 1
    await db.commit()

    return {
        "title":      conv.title,
        "messages":   json.loads(conv.messages) if conv.messages else [],
        "created_at": conv.created_at.isoformat(),
        "view_count": shared.view_count,
        "expires_at": shared.expires_at.isoformat() if shared.expires_at else None,
    }
