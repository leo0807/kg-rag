"""
J2.2: Analytics API — usage, quality, knowledge, and operations insights.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import User
from ..db.session import get_db
from ..services.analytics.insights_engine import insights_engine
from ..services.analytics.nl_to_sql import nl_to_sql

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

PERIODS = ["7d", "30d", "90d", "1y"]


@router.get("/usage")
async def usage_insights(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y)$"),
    tenant_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    effective_tenant = tenant_id or getattr(user, "tenant_id", None)
    return await insights_engine.usage_insights(db, period, effective_tenant)


@router.get("/quality")
async def quality_insights(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return await insights_engine.quality_insights(db, period)


@router.get("/knowledge")
async def knowledge_insights(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return await insights_engine.knowledge_insights(db, period)


@router.get("/operations")
async def operations_insights(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return await insights_engine.operations_insights(db, period)


# J4.2: Natural language query
from pydantic import BaseModel  # noqa: E402


class NLQueryRequest(BaseModel):
    question: str = ""
    raw_sql: str = ""


@router.post("/nl-query")
async def nl_query(
    body: NLQueryRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if body.raw_sql:
        from ..services.analytics.report_engine import _validate_sql
        try:
            _validate_sql(body.raw_sql)
        except ValueError as e:
            return {"error": str(e), "sql": body.raw_sql, "data": [], "columns": [], "viz_type": "table"}
        from sqlalchemy import text
        result = await db.execute(text(body.raw_sql + " LIMIT 200"))
        cols = list(result.keys())
        rows = [dict(zip(cols, row)) for row in result.fetchall()]
        viz = nl_to_sql._recommend_viz(rows, cols)
        return {"sql": body.raw_sql, "data": rows, "columns": cols, "viz_type": viz,
                "viz_config": nl_to_sql._build_viz_config(viz, cols)}
    return await nl_to_sql.query(body.question, db)
