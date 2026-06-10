"""
G7.2 隔离审计 API
GET /api/platform/isolation-audit — 执行隔离扫描并返回报告
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_current_user
from ...db.models import User
from ...db.session import get_db

router = APIRouter(prefix="/api/platform", tags=["platform-isolation"])
logger = logging.getLogger(__name__)

# 需要检查的表及其主键和 tenant_id 列
_AUDIT_TABLES = [
    ("users",           "id"),
    ("conversations",   "id"),
    ("audit_logs",      "id"),
    ("favorites",       "id"),
    ("user_notes",      "id"),
    ("eval_datasets",   "id"),
    ("eval_runs",       "id"),
    ("generation_tasks","id"),
    ("spec_templates",  "id"),
]


def _require_platform(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(403, "需要平台超管权限")
    return user


async def _check_table(db: AsyncSession, table: str, pk: str) -> dict:
    try:
        # 检查是否存在 tenant_id 列
        col_check = await db.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=:t AND column_name='tenant_id'"
        ), {"t": table})
        if not col_check.fetchone():
            return {"table": table, "status": "no_column", "issues": 0}

        # 统计 tenant_id 为 NULL 的记录
        null_count = (
            await db.execute(text(f'SELECT COUNT(*) FROM "{table}" WHERE tenant_id IS NULL'))
        ).scalar() or 0

        total = (
            await db.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
        ).scalar() or 0

        return {
            "table": table,
            "status": "ok" if null_count == 0 else "has_nulls",
            "total": total,
            "null_tenant_id": null_count,
            "coverage_pct": round((total - null_count) / max(total, 1) * 100, 1),
        }
    except Exception as e:
        return {"table": table, "status": "error", "error": str(e)}


@router.get("/isolation-audit")
async def isolation_audit(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_platform),
):
    results = []
    for table, pk in _AUDIT_TABLES:
        result = await _check_table(db, table, pk)
        results.append(result)

    issues = [r for r in results if r.get("null_tenant_id", 0) > 0]
    total_nulls = sum(r.get("null_tenant_id", 0) for r in results)

    return {
        "audit_time": datetime.utcnow().isoformat(),
        "tables_checked": len(results),
        "tables_with_issues": len(issues),
        "total_null_tenant_records": total_nulls,
        "health": "ok" if total_nulls == 0 else "warning",
        "details": results,
    }
