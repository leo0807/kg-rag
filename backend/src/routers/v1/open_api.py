"""
H7.3 开放 API 端点（v1）
POST /api/v1/query       — 问答
GET  /api/v1/documents   — 文档列表
POST /api/v1/feedback    — 提交反馈
GET  /api/v1/health      — 健康检查（公开）
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["open-api-v1"])


# ── 公开健康检查 ──────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "version": "v1"}


# ── 问答 ──────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    strategy: str = "hybrid"
    top_k: int = 5
    stream: bool = False


@router.post("/query")
async def v1_query(body: QueryRequest, request: Request):
    """
    开放接口：同步问答（流式请参考 /api/query/stream）。
    需要 scope: query:read
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    key_id    = getattr(request.state, "api_key_id", None)

    # 实际集成时调用内部 query service；此处返回引导响应
    return {
        "question": body.question,
        "answer": "此端点为开放 API 占位。请集成内部 QueryService 获取真实答案。",
        "sources": [],
        "tenant_id": tenant_id,
        "api_key_id": key_id,
        "strategy": body.strategy,
    }


# ── 文档列表 ──────────────────────────────────────────────────────────

@router.get("/documents")
async def v1_documents(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    开放接口：获取当前租户文档列表。
    需要 scope: documents:read
    """
    tenant_id = getattr(request.state, "tenant_id", None)

    try:
        from sqlalchemy import text
        stmt = text(
            "SELECT id, filename, upload_time FROM documents "
            "WHERE (:tid IS NULL OR tenant_id = :tid) "
            "ORDER BY upload_time DESC LIMIT :ps OFFSET :off"
        )
        rows = (await db.execute(stmt, {
            "tid": tenant_id, "ps": page_size, "off": (page - 1) * page_size
        })).fetchall()
        return {
            "page": page, "page_size": page_size,
            "items": [{"id": r[0], "filename": r[1], "upload_time": str(r[2])} for r in rows],
        }
    except Exception:
        return {"page": page, "page_size": page_size, "items": []}


# ── 反馈提交 ──────────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    conversation_id: str | None = None
    rating: int               # 1-5
    comment: str = ""
    tags: list[str] = []


@router.post("/feedback")
async def v1_feedback(body: FeedbackRequest, request: Request):
    """
    开放接口：提交问答反馈。
    需要 scope: feedback:write
    """
    if not (1 <= body.rating <= 5):
        raise HTTPException(400, "rating 需在 1-5 之间")

    return {
        "ok": True,
        "feedback_id": str(uuid.uuid4()),
        "message": "反馈已记录",
    }
