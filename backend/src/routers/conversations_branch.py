"""
Branch a conversation from a specific AI message (identified by message UUID).

POST /api/conversations/{conversation_id}/branch
Body: { "message_id": "<uuid>" }
Response: { "branch_id": str, "title": str }
"""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import Conversation, User
from ..db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class BranchByMessageRequest(BaseModel):
    message_id: str


@router.post("/{conversation_id}/branch")
async def branch_from_message(
    conversation_id: str,
    req: BranchByMessageRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new conversation branched from a specific message in an existing one."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "对话不存在")

    source_messages: list[dict] = json.loads(source.messages) if source.messages else []

    # Find the index of the target message by its id field
    target_index = next(
        (i for i, m in enumerate(source_messages) if m.get("id") == req.message_id),
        None,
    )
    if target_index is None:
        raise HTTPException(400, "消息不存在")

    branch_messages = source_messages[: target_index + 1]
    branch_title = f"分支: {source.title or '对话'}"

    branch = Conversation(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=branch_title,
        strategy=source.strategy,
        messages=json.dumps(branch_messages, ensure_ascii=False),
        parent_conversation_id=conversation_id,
        branch_point_message_id=req.message_id,
        # also populate legacy index fields for compatibility
        branch_from_conversation_id=conversation_id,
        branch_from_message_index=target_index,
    )
    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    logger.info(
        "Branch created: %s from %s at message %s",
        branch.id,
        conversation_id,
        req.message_id,
    )
    return {"branch_id": branch.id, "title": branch.title}
