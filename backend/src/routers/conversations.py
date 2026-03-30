"""
src/routers/conversations.py
多轮对话会话管理（按用户隔离，存储在 PostgreSQL）
"""
import json
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from ..db.session import get_db
from ..db.models  import Conversation
from ..auth.deps  import get_current_user
from ..db.models  import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title:    str       = "新对话"
    strategy: str       = "parallel"


class MessageAdd(BaseModel):
    messages: list[dict]
    title:    str = ""


@router.get("")
async def list_conversations(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(desc(Conversation.updated_at))
        .limit(50)
    )
    convs = result.scalars().all()
    return [
        {
            "id":         c.id,
            "title":      c.title,
            "messages":   json.loads(c.messages),
            "strategy":   c.strategy,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in convs
    ]


@router.post("")
async def create_conversation(
    req:  ConversationCreate,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    conv = Conversation(
        id       = str(uuid.uuid4()),
        user_id  = user.id,
        title    = req.title,
        strategy = req.strategy,
        messages = "[]",
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return {
        "id":       conv.id,
        "title":    conv.title,
        "messages": [],
        "strategy": conv.strategy,
    }


@router.put("/{conv_id}")
async def update_conversation(
    conv_id: str,
    req:     MessageAdd,
    db:      AsyncSession = Depends(get_db),
    user:    User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")

    conv.messages = json.dumps(req.messages, ensure_ascii=False)
    if req.title:
        conv.title = req.title
    conv.updated_at = datetime.now()
    await db.commit()
    return {"status": "OK"}


@router.delete("/{conv_id}")
async def delete_conversation(
    conv_id: str,
    db:      AsyncSession = Depends(get_db),
    user:    User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")
    await db.delete(conv)
    await db.commit()
    return {"status": "OK"}