"""User preferences API — GET /api/preferences, PUT /api/preferences"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import User
from ..db.session import get_db
from ..db.ux_models import UserPreferences

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PrefsIn(BaseModel):
    theme: str | None = None
    language: str | None = None
    default_strategy: str | None = None
    show_sources: bool | None = None
    show_metrics: bool | None = None
    answer_style: str | None = None
    ui_density: str | None = None


def _defaults(user_id: str) -> UserPreferences:
    return UserPreferences(user_id=user_id)


@router.get("")
async def get_preferences(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(UserPreferences, user.id)
    if not row:
        row = _defaults(user.id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return {
        "theme": row.theme,
        "language": row.language,
        "default_strategy": row.default_strategy,
        "show_sources": row.show_sources,
        "show_metrics": row.show_metrics,
        "answer_style": row.answer_style,
        "ui_density": row.ui_density,
    }


@router.put("")
async def update_preferences(
    body: PrefsIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(UserPreferences, user.id)
    if not row:
        row = _defaults(user.id)
        db.add(row)

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(row, field, val)

    await db.commit()
    await db.refresh(row)
    return {"ok": True}
