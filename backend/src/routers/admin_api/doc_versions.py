"""F6 — Document version control API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user, get_current_user
from ...db.models import User
from ...db.session import get_db
from ...db.version_models import DocumentVersion

router = APIRouter(prefix="/api/documents/versions", tags=["doc-versions"])


def _fmt(v: DocumentVersion) -> dict:
    return {
        "id": v.id, "doc_id": v.doc_id, "version_num": v.version_num,
        "title": v.title, "summary": v.summary,
        "change_summary": v.change_summary, "changed_by": v.changed_by,
        "created_at": v.created_at.isoformat(),
    }


@router.get("/{doc_id}")
async def list_versions(
    doc_id: str,
    _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    rows = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.doc_id == doc_id)
        .order_by(DocumentVersion.version_num.desc())
    )).scalars().all()
    return [_fmt(v) for v in rows]


class SnapshotCreate(BaseModel):
    title: str | None = None
    summary: str | None = None
    metadata_snapshot: dict | None = None
    change_summary: str | None = None


@router.post("/{doc_id}")
async def create_version(
    doc_id: str, body: SnapshotCreate,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    max_ver = (await db.execute(
        select(func.max(DocumentVersion.version_num))
        .where(DocumentVersion.doc_id == doc_id)
    )).scalar() or 0
    v = DocumentVersion(
        doc_id=doc_id, version_num=max_ver + 1,
        title=body.title, summary=body.summary,
        metadata_snapshot=body.metadata_snapshot,
        change_summary=body.change_summary,
        changed_by=user.username,
    )
    db.add(v)
    await db.commit()
    return _fmt(v)


@router.get("/{doc_id}/{version_num}")
async def get_version(
    doc_id: str, version_num: int,
    _user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    v = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.doc_id == doc_id,
               DocumentVersion.version_num == version_num)
    )).scalar_one_or_none()
    if not v:
        raise HTTPException(404, "版本不存在")
    return {**_fmt(v), "metadata_snapshot": v.metadata_snapshot}
