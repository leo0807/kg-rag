"""
src/routers/favorites.py
用户收藏夹 CRUD
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import Favorite, User
from ..db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/favorites", tags=["favorites"])


# ── Pydantic 模型 ──────────────────────────────────────────────────────────

class FavoriteCreate(BaseModel):
    type:        str                # section | document | query
    doc_id:      str | None = None
    section_id:  str | None = None
    query_text:  str | None = None
    title:       str
    note:        str | None = None


class FavoritePatch(BaseModel):
    note: str | None = None


# ── 接口 ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_favorites(
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """返回当前用户所有收藏，按 created_at 倒序。"""
    result = await db.execute(
        select(Favorite)
        .where(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
    )
    rows = result.scalars().all()
    return [_serialize(f) for f in rows]


@router.post("", status_code=status.HTTP_200_OK)
async def create_favorite(
    body:         FavoriteCreate,
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """
    新增收藏。若同一用户对同一 section_id / query_text 已收藏，返回已有记录（幂等）。
    """
    if body.type not in ("section", "document", "query"):
        raise HTTPException(400, "type 必须为 section / document / query")

    # 幂等检查
    dupe_filter = [Favorite.user_id == current_user.id]
    if body.type == "section"  and body.section_id:
        dupe_filter.append(Favorite.section_id == body.section_id)
    elif body.type == "document" and body.doc_id:
        dupe_filter.append(and_(Favorite.type == "document", Favorite.doc_id == body.doc_id))
    elif body.type == "query"  and body.query_text:
        dupe_filter.append(Favorite.query_text == body.query_text)

    if len(dupe_filter) > 1:
        existing = (await db.execute(select(Favorite).where(*dupe_filter))).scalar_one_or_none()
        if existing:
            return _serialize(existing)

    fav = Favorite(
        user_id    = current_user.id,
        type       = body.type,
        doc_id     = body.doc_id,
        section_id = body.section_id,
        query_text = body.query_text,
        title      = body.title,
        note       = body.note,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)
    return _serialize(fav)


@router.delete("/{fav_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite(
    fav_id:       str,
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """删除收藏（只能删除自己的）。"""
    fav = (await db.execute(
        select(Favorite).where(Favorite.id == fav_id, Favorite.user_id == current_user.id)
    )).scalar_one_or_none()
    if not fav:
        raise HTTPException(404, "收藏不存在")
    await db.delete(fav)
    await db.commit()


@router.patch("/{fav_id}")
async def patch_favorite(
    fav_id:       str,
    body:         FavoritePatch,
    current_user: User        = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """更新备注（只能更新自己的）。"""
    fav = (await db.execute(
        select(Favorite).where(Favorite.id == fav_id, Favorite.user_id == current_user.id)
    )).scalar_one_or_none()
    if not fav:
        raise HTTPException(404, "收藏不存在")
    fav.note = body.note
    await db.commit()
    await db.refresh(fav)
    return _serialize(fav)


# ── 序列化 ─────────────────────────────────────────────────────────────────

def _serialize(f: Favorite) -> dict:
    return {
        "id":          f.id,
        "type":        f.type,
        "doc_id":      f.doc_id,
        "section_id":  f.section_id,
        "query_text":  f.query_text,
        "title":       f.title,
        "note":        f.note,
        "created_at":  f.created_at.isoformat() if f.created_at else None,
    }
