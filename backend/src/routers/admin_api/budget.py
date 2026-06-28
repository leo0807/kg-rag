"""
Token budget management and alert endpoints.

GET  /api/admin/llm-costs/budget-status  — 各部门预算消耗进度
POST /api/admin/llm-costs/budget         — 设置或更新部门预算
POST /api/admin/llm-costs/budget/check   — 手动触发一次预算检查
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import LLMUsage, SystemSetting, User
from ...db.session import get_db
from ...services.monitoring.alert_sender import AlertSender

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/llm-costs", tags=["admin-budget"])

_FALLBACK_MODEL_KEY = "llm_budget_fallback_model"
_DEFAULT_FALLBACK   = os.getenv("LLM_FALLBACK_MODEL", "claude-haiku-4-5-20251001")

_sender = AlertSender()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_budget(db: AsyncSession, department: str) -> float | None:
    row = await db.scalar(
        select(SystemSetting.value).where(SystemSetting.key == f"budget_usd_{department}")
    )
    try:
        return float(row) if row else None
    except (TypeError, ValueError):
        return None


async def _get_month_spend(db: AsyncSession, department: str) -> float:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.scalar(
        select(func.sum(LLMUsage.cost_usd)).where(
            LLMUsage.department == department,
            LLMUsage.created_at >= start,
        )
    )
    return float(result or 0)


async def _list_departments(db: AsyncSession) -> list[str]:
    rows = await db.execute(
        select(LLMUsage.department).distinct().where(LLMUsage.department.isnot(None))
    )
    return [r[0] for r in rows if r[0]]


async def _check_and_alert(db: AsyncSession, department: str) -> dict[str, Any]:
    budget = await _get_budget(db, department)
    spend  = await _get_month_spend(db, department)

    if budget is None or budget <= 0:
        return {"department": department, "spend": spend, "budget": None, "status": "no_budget"}

    ratio = spend / budget
    status = "ok"

    if ratio >= 1.0:
        status = "exceeded"
        await _sender.send(
            f"[CRITICAL] 部门 {department} LLM 月度预算已超支: "
            f"消耗 ${spend:.2f} / 预算 ${budget:.2f} ({ratio:.0%})",
            level="critical",
        )
        # Write fallback model flag to SystemSetting
        try:
            fallback = await db.scalar(
                select(SystemSetting.value).where(SystemSetting.key == _FALLBACK_MODEL_KEY)
            ) or _DEFAULT_FALLBACK
            log.warning("Budget exceeded for %s — activating fallback model %s", department, fallback)
        except Exception:
            pass

    elif ratio >= 0.8:
        status = "warning"
        await _sender.send(
            f"[WARN] 部门 {department} LLM 月度预算消耗达 {ratio:.0%}: "
            f"${spend:.2f} / ${budget:.2f}",
            level="warning",
        )

    return {
        "department":  department,
        "spend_usd":   round(spend, 4),
        "budget_usd":  round(budget, 4),
        "ratio":       round(ratio, 4),
        "status":      status,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/budget-status")
async def get_budget_status(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return budget consumption progress for all departments."""
    departments = await _list_departments(db)
    if not departments:
        return {"departments": [], "total_departments": 0}

    results = []
    for dept in departments:
        results.append(await _check_and_alert(db, dept))

    return {
        "as_of":             datetime.now(timezone.utc).isoformat(),
        "total_departments": len(results),
        "departments":       results,
    }


class BudgetBody(BaseModel):
    department: str
    budget_usd: float


@router.post("/budget")
async def set_budget(
    body: BudgetBody,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Set or update a department's monthly USD budget."""
    key = f"budget_usd_{body.department}"
    existing = await db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if existing:
        existing.value = str(body.budget_usd)
    else:
        db.add(SystemSetting(key=key, value=str(body.budget_usd)))
    await db.commit()
    return {"ok": True, "department": body.department, "budget_usd": body.budget_usd}


@router.post("/budget/check")
async def manual_budget_check(
    department: str | None = None,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Manually trigger a budget check and send alerts if thresholds exceeded."""
    departments = [department] if department else await _list_departments(db)
    results = [await _check_and_alert(db, d) for d in departments]
    return {"checked": len(results), "results": results}
