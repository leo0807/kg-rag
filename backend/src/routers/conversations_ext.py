"""
会话管理增强 API — 分类、置顶、归档、标签、全文搜索
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import Conversation, User
from ..db.session import get_db
from ..db.ux_models import ConversationCategory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ── Pydantic ──────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name:  str
    color: str = "#6366f1"
    icon:  str = "folder"

class CategoryPatch(BaseModel):
    name:  str | None = None
    color: str | None = None
    icon:  str | None = None

class TagsUpdate(BaseModel):
    tags: list[str]

class CategoryMove(BaseModel):
    category_id: str | None = None


# ── Category CRUD ─────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(ConversationCategory)
        .where(ConversationCategory.user_id == user.id)
        .order_by(ConversationCategory.created_at)
    )
    cats = result.scalars().all()
    # count conversations per category
    conv_result = await db.execute(
        select(Conversation.category_id)
        .where(Conversation.user_id == user.id, Conversation.is_archived == False)
    )
    counts: dict[str, int] = {}
    for (cat_id,) in conv_result.all():
        if cat_id:
            counts[cat_id] = counts.get(cat_id, 0) + 1
    return [
        {"id": c.id, "name": c.name, "color": c.color, "icon": c.icon,
         "count": counts.get(c.id, 0), "created_at": c.created_at.isoformat()}
        for c in cats
    ]


@router.post("/categories")
async def create_category(
    req:  CategoryCreate,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    cat = ConversationCategory(
        id=str(uuid.uuid4()), user_id=user.id,
        name=req.name, color=req.color, icon=req.icon,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "color": cat.color, "icon": cat.icon}


@router.put("/categories/{cat_id}")
async def update_category(
    cat_id: str,
    req:    CategoryPatch,
    db:     AsyncSession = Depends(get_db),
    user:   User         = Depends(get_current_user),
):
    result = await db.execute(
        select(ConversationCategory).where(
            ConversationCategory.id == cat_id,
            ConversationCategory.user_id == user.id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(404, "分类不存在")
    if req.name  is not None: cat.name  = req.name
    if req.color is not None: cat.color = req.color
    if req.icon  is not None: cat.icon  = req.icon
    await db.commit()
    return {"status": "ok"}


@router.delete("/categories/{cat_id}")
async def delete_category(
    cat_id: str,
    db:     AsyncSession = Depends(get_db),
    user:   User         = Depends(get_current_user),
):
    result = await db.execute(
        select(ConversationCategory).where(
            ConversationCategory.id == cat_id,
            ConversationCategory.user_id == user.id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(404, "分类不存在")
    # clear category_id on owned conversations
    convs_result = await db.execute(
        select(Conversation).where(
            Conversation.user_id == user.id,
            Conversation.category_id == cat_id,
        )
    )
    for conv in convs_result.scalars().all():
        conv.category_id = None
    await db.delete(cat)
    await db.commit()
    return {"status": "ok"}


# ── Conversation metadata ─────────────────────────────────────────────────────

def _get_conv(db: AsyncSession, conv_id: str, user_id: str):
    return db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == user_id
        )
    )


@router.put("/{conv_id}/category")
async def set_category(
    conv_id: str, req: CategoryMove,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    result = await _get_conv(db, conv_id, user.id)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")
    conv.category_id = req.category_id
    await db.commit()
    return {"status": "ok"}


@router.put("/{conv_id}/pin")
async def toggle_pin(
    conv_id: str,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    result = await _get_conv(db, conv_id, user.id)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")
    conv.is_pinned = not conv.is_pinned
    await db.commit()
    return {"is_pinned": conv.is_pinned}


@router.put("/{conv_id}/archive")
async def toggle_archive(
    conv_id: str,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    result = await _get_conv(db, conv_id, user.id)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")
    conv.is_archived = not conv.is_archived
    await db.commit()
    return {"is_archived": conv.is_archived}


@router.put("/{conv_id}/tags")
async def update_tags(
    conv_id: str, req: TagsUpdate,
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    result = await _get_conv(db, conv_id, user.id)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")
    conv.tags = req.tags
    await db.commit()
    return {"tags": conv.tags}


# ── Full-text search ──────────────────────────────────────────────────────────

@router.get("/search")
async def search_conversations(
    q:           str        = Query("", min_length=0),
    category_id: str | None = Query(None),
    archived:    bool       = Query(False),
    limit:       int        = Query(20, le=50),
    db:   AsyncSession      = Depends(get_db),
    user: User              = Depends(get_current_user),
):
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == user.id,
            Conversation.is_archived == archived,
        )
        .order_by(desc(Conversation.updated_at))
        .limit(200)
    )
    if category_id:
        stmt = stmt.where(Conversation.category_id == category_id)
    result = await db.execute(stmt)
    convs = result.scalars().all()

    matched = []
    q_lower = q.lower()
    for c in convs:
        msgs: list[dict] = json.loads(c.messages) if c.messages else []
        highlight = ""
        matched_messages: list[Any] = []

        if not q_lower or q_lower in c.title.lower():
            highlight = c.title
        else:
            for m in msgs:
                txt = m.get("content", "")
                if q_lower and q_lower in txt.lower():
                    idx = txt.lower().find(q_lower)
                    snip = txt[max(0, idx - 30): idx + 80]
                    highlight = snip.replace(
                        txt[idx: idx + len(q_lower)],
                        f"<mark>{txt[idx: idx + len(q_lower)]}</mark>",
                    )
                    matched_messages.append({"role": m.get("role"), "snippet": snip})
                    break

        if q_lower and not highlight and not matched_messages:
            continue

        matched.append({
            "id": c.id, "title": c.title,
            "highlight": highlight or c.title,
            "matched_messages": matched_messages,
            "category_id": c.category_id,
            "is_pinned": c.is_pinned,
            "tags": c.tags or [],
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        })
        if len(matched) >= limit:
            break

    return {"conversations": matched, "total": len(matched)}
