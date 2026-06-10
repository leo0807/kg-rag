"""
用户笔记 CRUD — 关联到章节或消息的私有/团队笔记
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.session import get_db
from ..db.ux_models import UserNote
from ..db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteCreate(BaseModel):
    title:              str
    content:            str  = ""
    related_chunk_id:   str | None = None
    related_message_id: str | None = None
    tags:               list[str]  = []
    visibility:         str        = "private"


class NotePatch(BaseModel):
    title:      str | None       = None
    content:    str | None       = None
    tags:       list[str] | None = None
    visibility: str | None       = None


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_notes(
    tag:   str | None = Query(None),
    q:     str | None = Query(None),
    limit: int        = Query(50, le=100),
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    stmt = (
        select(UserNote)
        .where(UserNote.user_id == user.id)
        .order_by(desc(UserNote.updated_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    notes = result.scalars().all()

    def matches(n: UserNote) -> bool:
        if tag and tag not in (n.tags or []):
            return False
        if q and q.lower() not in (n.title + n.content).lower():
            return False
        return True

    return [_serialize(n) for n in notes if matches(n)]


@router.post("")
async def create_note(
    req:  NoteCreate,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    note = UserNote(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=req.title,
        content=req.content,
        related_chunk_id=req.related_chunk_id,
        related_message_id=req.related_message_id,
        tags=req.tags,
        visibility=req.visibility,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return _serialize(note)


@router.get("/by-chunk/{chunk_id}")
async def notes_by_chunk(
    chunk_id: str,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    result = await db.execute(
        select(UserNote).where(
            UserNote.user_id == user.id,
            UserNote.related_chunk_id == chunk_id,
        )
    )
    return [_serialize(n) for n in result.scalars().all()]


@router.get("/{note_id}")
async def get_note(
    note_id: str,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    note = await _fetch(db, note_id, user.id)
    return _serialize(note)


@router.put("/{note_id}")
async def update_note(
    note_id: str,
    req:     NotePatch,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    note = await _fetch(db, note_id, user.id)
    if req.title      is not None: note.title      = req.title
    if req.content    is not None: note.content    = req.content
    if req.tags       is not None: note.tags       = req.tags
    if req.visibility is not None: note.visibility = req.visibility
    note.updated_at = datetime.now()
    await db.commit()
    return _serialize(note)


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    note = await _fetch(db, note_id, user.id)
    await db.delete(note)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{note_id}/export")
async def export_note(
    note_id: str,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    note = await _fetch(db, note_id, user.id)
    tags_line = f"> 标签: {', '.join(note.tags)}\n\n" if note.tags else ""
    md = (
        f"# {note.title}\n\n"
        f"> 创建时间: {note.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"{tags_line}"
        f"{note.content}"
    )
    safe = quote(note.title or "note", safe="")
    return Response(
        md.encode("utf-8"),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe}.md"},
    )


# ── helpers ───────────────────────────────────────────────────────────────────

async def _fetch(db: AsyncSession, note_id: str, user_id: str) -> UserNote:
    result = await db.execute(
        select(UserNote).where(UserNote.id == note_id, UserNote.user_id == user_id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(404, "笔记不存在")
    return note


def _serialize(n: UserNote) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "related_chunk_id": n.related_chunk_id,
        "related_message_id": n.related_message_id,
        "tags": n.tags or [],
        "visibility": n.visibility,
        "created_at": n.created_at.isoformat(),
        "updated_at": n.updated_at.isoformat(),
    }
