"""实体黑白名单管理 — CRUD + Redis 缓存同步"""
from __future__ import annotations
import json, logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..db.session import get_db
from ..db.models import EntityFilter
from ..auth.deps import get_admin_user, get_current_user
from ..db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/entity-filters", tags=["entity-filter"])

VALID_TYPES = {"blacklist", "whitelist"}


class FilterCreate(BaseModel):
    entity_name: str
    entity_type: str = ""
    filter_type: str   # blacklist | whitelist
    reason: str = ""


def _sync_redis(blacklist: list[str], whitelist: list[str]) -> None:
    try:
        import redis as _redis
        from ..core.config import settings
        r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.set("entity:blacklist", json.dumps(blacklist))
        r.set("entity:whitelist", json.dumps(whitelist))
    except Exception as e:
        logger.debug("Redis sync skipped: %s", e)


async def _get_all(db: AsyncSession) -> list[EntityFilter]:
    result = await db.execute(select(EntityFilter).order_by(EntityFilter.created_at.desc()))
    return list(result.scalars().all())


async def _refresh_redis(db: AsyncSession) -> None:
    rows = await _get_all(db)
    bl = [r.entity_name for r in rows if r.filter_type == "blacklist"]
    wl = [r.entity_name for r in rows if r.filter_type == "whitelist"]
    _sync_redis(bl, wl)


@router.get("")
async def list_filters(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    rows = await _get_all(db)
    return [{"id": r.id, "entity_name": r.entity_name, "entity_type": r.entity_type,
             "filter_type": r.filter_type, "reason": r.reason, "created_at": r.created_at.isoformat()} for r in rows]


@router.post("")
async def create_filter(req: FilterCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(get_admin_user)):
    if req.filter_type not in VALID_TYPES:
        raise HTTPException(400, f"filter_type 必须是 blacklist 或 whitelist")
    if not req.entity_name.strip():
        raise HTTPException(400, "entity_name 不能为空")
    rule = EntityFilter(
        entity_name=req.entity_name.strip(),
        entity_type=req.entity_type,
        filter_type=req.filter_type,
        reason=req.reason,
        created_by=admin.id,
    )
    db.add(rule)
    await db.flush()
    await db.commit()
    await _refresh_redis(db)
    return {"id": rule.id, "status": "OK"}


@router.delete("/{rule_id}")
async def delete_filter(rule_id: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_admin_user)):
    result = await db.execute(select(EntityFilter).where(EntityFilter.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "规则不存在")
    await db.execute(delete(EntityFilter).where(EntityFilter.id == rule_id))
    await db.commit()
    await _refresh_redis(db)
    return {"status": "OK"}
