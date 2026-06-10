"""
推荐 API — 基于当前对话生成延伸问题
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import Conversation, User
from ..db.session import get_db
from ..services.qa.question_recommender import get_recommender

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recommend", tags=["recommend"])


class RecommendRequest(BaseModel):
    conversation_id:   str
    current_message_id: str | None = None   # optional, unused for now


@router.post("/questions")
async def recommend_questions(
    req:  RecommendRequest,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id      == req.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "会话不存在")

    msgs: list[dict] = json.loads(conv.messages) if conv.messages else []
    if len(msgs) < 2:
        return {"questions": []}

    # find last user+assistant pair
    question = ""
    answer   = ""
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "assistant" and not answer:
            answer = msgs[i].get("content", "")
        elif msgs[i].get("role") == "user" and not question and answer:
            question = msgs[i].get("content", "")
            break

    if not question or not answer:
        return {"questions": []}

    recommender = get_recommender()
    questions   = await recommender.recommend(question, answer)
    return {"questions": questions}
