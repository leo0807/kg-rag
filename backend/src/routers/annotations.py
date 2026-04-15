"""
图谱节点批注 API
允许已登录用户为任意图谱节点添加现场心得或纠错备注。
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from ..db.session  import get_db
from ..db.models   import NodeAnnotation, User
from ..auth.deps   import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/annotations", tags=["annotations"])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class AnnotationCreate(BaseModel):
    node_id:   str
    node_type: str = ""
    content:   str


class AnnotationOut(BaseModel):
    id:          int
    node_id:     str
    node_type:   str
    user_id:     str
    username:    str
    full_name:   str
    content:     str
    created_at:  datetime
    updated_at:  datetime


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{node_id}", response_model=list[AnnotationOut])
async def list_annotations(
    node_id: str,
    db:      AsyncSession  = Depends(get_db),
    _user:   User          = Depends(get_current_user),
):
    """获取某节点的全部批注（时间正序）"""
    result = await db.execute(
        select(NodeAnnotation)
        .where(NodeAnnotation.node_id == node_id)
        .order_by(NodeAnnotation.created_at.asc())
    )
    rows = result.scalars().all()
    out  = []
    for a in rows:
        await db.refresh(a, ["user"])
        out.append(AnnotationOut(
            id          = a.id,
            node_id     = a.node_id,
            node_type   = a.node_type,
            user_id     = a.user_id,
            username    = a.user.username,
            full_name   = a.user.full_name or a.user.username,
            content     = a.content,
            created_at  = a.created_at,
            updated_at  = a.updated_at,
        ))
    return out


@router.post("", response_model=AnnotationOut, status_code=status.HTTP_201_CREATED)
async def create_annotation(
    body: AnnotationCreate,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """为节点新增一条批注"""
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="批注内容不能为空")

    ann = NodeAnnotation(
        node_id   = body.node_id,
        node_type = body.node_type,
        user_id   = user.id,
        content   = body.content.strip(),
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann, ["user"])

    logger.info("用户 %s 批注节点 %s", user.username, body.node_id)
    return AnnotationOut(
        id          = ann.id,
        node_id     = ann.node_id,
        node_type   = ann.node_type,
        user_id     = ann.user_id,
        username    = ann.user.username,
        full_name   = ann.user.full_name or ann.user.username,
        content     = ann.content,
        created_at  = ann.created_at,
        updated_at  = ann.updated_at,
    )


@router.delete("/{ann_id}")
async def delete_annotation(
    ann_id: int,
    db:     AsyncSession = Depends(get_db),
    user:   User         = Depends(get_current_user),
):
    """删除批注（仅本人或管理员可操作）"""
    result = await db.execute(
        select(NodeAnnotation).where(NodeAnnotation.id == ann_id)
    )
    ann = result.scalar_one_or_none()
    if ann is None:
        raise HTTPException(status_code=404, detail="批注不存在")
    if ann.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="无权删除他人批注")

    await db.execute(delete(NodeAnnotation).where(NodeAnnotation.id == ann_id))
    await db.commit()
    return {"ok": True}
