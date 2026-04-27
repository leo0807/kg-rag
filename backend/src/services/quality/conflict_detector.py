from __future__ import annotations

"""
规范冲突检测服务（公共接口）
- 两条检测路径：constraint（规则）和 semantic（LLM）
- 扫描任务：start_conflict_scan / get_scan / list_scans
- 持久化查询：list_conflicts / update_conflict_status / get_conflict_stats
"""

from typing import Any

from neo4j import Driver
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ConflictRecord
from .conflict_scan import start_conflict_scan, get_scan, list_scans  # noqa: F401

__all__ = [
    "start_conflict_scan", "get_scan", "list_scans",
    "list_conflicts", "update_conflict_status", "get_conflict_stats",
]


async def list_conflicts(
    db: AsyncSession,
    status: str | None = None,
    conflict_type: str | None = None,
    severity: str | None = None,
    scan_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ConflictRecord], int]:
    q = select(ConflictRecord)
    if status:
        q = q.where(ConflictRecord.status == status)
    if conflict_type:
        q = q.where(ConflictRecord.conflict_type == conflict_type)
    if severity:
        q = q.where(ConflictRecord.severity == severity)
    if scan_id:
        q = q.where(ConflictRecord.scan_id == scan_id)

    count_q = select(sqlfunc.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(ConflictRecord.created_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total


async def update_conflict_status(db: AsyncSession, conflict_id: int, status: str) -> ConflictRecord:
    valid = {"pending", "confirmed", "dismissed", "resolved"}
    if status not in valid:
        raise ValueError(f"status 必须是 {valid} 之一")
    result = await db.execute(select(ConflictRecord).where(ConflictRecord.id == conflict_id))
    record = result.scalar_one_or_none()
    if not record:
        raise KeyError(conflict_id)
    record.status = status
    await db.commit()
    await db.refresh(record)
    return record


async def get_conflict_stats(db: AsyncSession) -> dict[str, Any]:
    total = (await db.execute(select(sqlfunc.count()).select_from(ConflictRecord))).scalar() or 0
    by_status = (await db.execute(
        select(ConflictRecord.status, sqlfunc.count()).group_by(ConflictRecord.status)
    )).all()
    by_severity = (await db.execute(
        select(ConflictRecord.severity, sqlfunc.count()).group_by(ConflictRecord.severity)
    )).all()
    by_type = (await db.execute(
        select(ConflictRecord.conflict_type, sqlfunc.count()).group_by(ConflictRecord.conflict_type)
    )).all()
    return {
        "total": total,
        "by_status": dict(by_status),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
    }
