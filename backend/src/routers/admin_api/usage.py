"""
GET /api/admin/usage — Token 用量监控仪表板

数据来源双轨：
  主轨 · Langfuse /api/public/metrics/daily  → 按天 token 趋势、模型分布、请求数
  副轨 · LLMUsage PostgreSQL 表              → 精确延迟、本地费用估算
"""
from __future__ import annotations

import logging
import os
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import LLMUsage, User
from ...db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

# ── Langfuse 配置 ─────────────────────────────────────────────────────────────

def _langfuse_auth() -> str | None:
    pub = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sec = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not pub or not sec:
        return None
    return "Basic " + b64encode(f"{pub}:{sec}".encode()).decode()


def _langfuse_host() -> str:
    return os.getenv("LANGFUSE_HOST", "http://localhost:3001").rstrip("/")


# 已知模型每 1K token 价格（USD）
_MODEL_PRICE: dict[str, tuple[float, float]] = {
    "gpt-4o":                 (0.005,  0.015),
    "gpt-4o-mini":            (0.00015, 0.0006),
    "gpt-4-turbo":            (0.01,   0.03),
    "claude-3-5-sonnet":      (0.003,  0.015),
    "claude-3-haiku":         (0.00025, 0.00125),
    "qwen2.5-7b":             (0.0,    0.0),
    "qwen/qwen2.5-7b":        (0.0,    0.0),
    "qwen-plus":              (0.0004, 0.0012),
    "deepseek-chat":          (0.00014, 0.00028),
    "deepseek-v3":            (0.00027, 0.0011),
}

def _model_cost(model: str, input_tok: int, output_tok: int) -> float:
    key = model.lower()
    for pattern, (inp_price, out_price) in _MODEL_PRICE.items():
        if pattern in key:
            return (input_tok / 1000) * inp_price + (output_tok / 1000) * out_price
    return 0.0


# ── Langfuse 拉取 ─────────────────────────────────────────────────────────────

async def _fetch_langfuse_daily(days: int = 7) -> list[dict[str, Any]]:
    auth = _langfuse_auth()
    if not auth:
        return []
    url = f"{_langfuse_host()}/api/public/metrics/daily?unit=TOKENS&limit={days + 1}"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, headers={"Authorization": auth})
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as exc:
        logger.warning("Langfuse metrics/daily 请求失败: %s", exc)
        return []


# ── PostgreSQL 拉取 ───────────────────────────────────────────────────────────

async def _pg_period(db: AsyncSession, since: datetime) -> dict[str, Any]:
    result = await db.execute(
        select(
            func.count(LLMUsage.id).label("requests"),
            func.coalesce(func.sum(LLMUsage.prompt_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LLMUsage.completion_tokens), 0).label("output_tokens"),
            func.coalesce(func.avg(LLMUsage.latency_ms), 0).label("avg_latency_ms"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0).label("cost_usd"),
        ).where(LLMUsage.created_at >= since)
    )
    row = result.one()
    return {
        "requests":       int(row.requests or 0),
        "input_tokens":   int(row.input_tokens or 0),
        "output_tokens":  int(row.output_tokens or 0),
        "avg_latency_ms": round(float(row.avg_latency_ms or 0)),
        "cost_usd":       round(float(row.cost_usd or 0), 4),
    }


async def _pg_model_dist(db: AsyncSession, since: datetime) -> list[dict[str, Any]]:
    result = await db.execute(
        select(
            LLMUsage.model,
            func.count(LLMUsage.id).label("requests"),
            func.coalesce(func.sum(LLMUsage.prompt_tokens + LLMUsage.completion_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0).label("cost_usd"),
        )
        .where(LLMUsage.created_at >= since)
        .where(LLMUsage.model != "")
        .group_by(LLMUsage.model)
        .order_by(func.count(LLMUsage.id).desc())
    )
    return [
        {
            "model":    str(r.model),
            "requests": int(r.requests or 0),
            "tokens":   int(r.tokens or 0),
            "cost_usd": round(float(r.cost_usd or 0), 4),
        }
        for r in result.all()
    ]


async def _pg_daily_trend(db: AsyncSession, days: int = 7) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(LLMUsage.created_at).label("date"),
            func.count(LLMUsage.id).label("requests"),
            func.coalesce(func.sum(LLMUsage.prompt_tokens + LLMUsage.completion_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0).label("cost_usd"),
            func.coalesce(func.avg(LLMUsage.latency_ms), 0).label("avg_latency_ms"),
        )
        .where(LLMUsage.created_at >= since)
        .group_by(func.date(LLMUsage.created_at))
        .order_by(func.date(LLMUsage.created_at))
    )
    return [
        {
            "date":          str(r.date),
            "requests":      int(r.requests or 0),
            "tokens":        int(r.tokens or 0),
            "cost_usd":      round(float(r.cost_usd or 0), 4),
            "avg_latency_ms": round(float(r.avg_latency_ms or 0)),
        }
        for r in result.all()
    ]


# ── Langfuse 解析 → daily_trend + model_dist 补全 ────────────────────────────

def _parse_langfuse_trend(daily_data: list[dict]) -> list[dict[str, Any]]:
    trend: list[dict[str, Any]] = []
    for day in daily_data:
        total_in = sum(u.get("inputUsage", 0) for u in day.get("usage", []))
        total_out = sum(u.get("outputUsage", 0) for u in day.get("usage", []))
        model_costs = sum(
            _model_cost(u.get("model", ""), u.get("inputUsage", 0), u.get("outputUsage", 0))
            for u in day.get("usage", [])
        )
        trend.append({
            "date":     day["date"],
            "requests": day.get("countTraces", 0),
            "tokens":   total_in + total_out,
            "input_tokens":  total_in,
            "output_tokens": total_out,
            "cost_usd": round(model_costs, 4),
        })
    return sorted(trend, key=lambda x: x["date"])


def _parse_langfuse_models(daily_data: list[dict]) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = {}
    for day in daily_data:
        for u in day.get("usage", []):
            model = u.get("model", "unknown")
            if model not in agg:
                agg[model] = {"model": model, "requests": 0, "tokens": 0, "cost_usd": 0.0}
            inp = u.get("inputUsage", 0)
            out = u.get("outputUsage", 0)
            agg[model]["requests"] += u.get("countObservations", 0)
            agg[model]["tokens"] += inp + out
            agg[model]["cost_usd"] += _model_cost(model, inp, out)
    for m in agg.values():
        m["cost_usd"] = round(m["cost_usd"], 4)
    return sorted(agg.values(), key=lambda x: x["requests"], reverse=True)


async def _pg_user_dist(db: AsyncSession, since: datetime) -> list[dict[str, Any]]:
    result = await db.execute(
        select(
            LLMUsage.user_id,
            User.username,
            User.department,
            func.count(LLMUsage.id).label("requests"),
            func.coalesce(func.sum(LLMUsage.prompt_tokens + LLMUsage.completion_tokens), 0).label("tokens"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0.0).label("cost_usd"),
            func.max(LLMUsage.created_at).label("last_active"),
        )
        .outerjoin(User, LLMUsage.user_id == User.id)
        .where(LLMUsage.created_at >= since)
        .where(LLMUsage.user_id.isnot(None))
        .group_by(LLMUsage.user_id, User.username, User.department)
        .order_by(func.count(LLMUsage.id).desc())
    )
    return [
        {
            "user_id":    r.user_id,
            "username":   r.username or r.user_id,
            "department": r.department or "",
            "requests":   int(r.requests or 0),
            "tokens":     int(r.tokens or 0),
            "cost_usd":   round(float(r.cost_usd or 0), 4),
            "last_active": r.last_active.strftime("%H:%M") if r.last_active else None,
        }
        for r in result.all()
    ]


@router.get("/usage/users")
async def usage_users(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=7)
    today_rows, week_rows = await _pg_user_dist(db, today_start), await _pg_user_dist(db, week_start)
    today_map = {r["user_id"]: r for r in today_rows}
    week_map  = {r["user_id"]: r for r in week_rows}
    all_ids = sorted(set(today_map) | set(week_map),
                     key=lambda uid: week_map.get(uid, {}).get("requests", 0), reverse=True)
    users = []
    for uid in all_ids:
        t, w = today_map.get(uid, {}), week_map.get(uid, {})
        users.append({
            "user_id":       uid,
            "username":      t.get("username") or w.get("username") or uid,
            "department":    t.get("department") or w.get("department") or "",
            "today_requests": t.get("requests", 0),
            "today_tokens":   t.get("tokens", 0),
            "today_cost_usd": round(t.get("cost_usd", 0), 4),
            "week_requests":  w.get("requests", 0),
            "week_tokens":    w.get("tokens", 0),
            "week_cost_usd":  round(w.get("cost_usd", 0), 4),
            "last_active":    t.get("last_active") or w.get("last_active"),
        })
    return {"users": users, "total_users": len(users), "active_today": len(today_map)}


# ── 主接口 ────────────────────────────────────────────────────────────────────

@router.get("/usage")
async def usage_dashboard(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=7)

    # ── PostgreSQL 数据（精确延迟 + 费用）────────────────────────────────────
    today_pg, week_pg, pg_models, pg_trend = await _pg_period(db, today_start), \
        await _pg_period(db, week_start), \
        await _pg_model_dist(db, week_start), \
        await _pg_daily_trend(db, 7)

    # ── Langfuse 数据（按天趋势，作为主要 token 来源）────────────────────────
    lf_daily = await _fetch_langfuse_daily(days=9)
    lf_trend = _parse_langfuse_trend(lf_daily)
    lf_models = _parse_langfuse_models(lf_daily)

    # ── 今日/本周：优先用 PostgreSQL（更精确）────────────────────────────────
    # 若 PG token 为 0，尝试从 Langfuse 补充
    today_str = today_start.date().isoformat()
    if today_pg["input_tokens"] == 0:
        lf_today = next((d for d in lf_trend if d["date"] == today_str), None)
        if lf_today:
            today_pg["input_tokens"] = lf_today.get("input_tokens", 0)
            today_pg["output_tokens"] = lf_today.get("output_tokens", 0)
            if today_pg["cost_usd"] == 0:
                today_pg["cost_usd"] = lf_today.get("cost_usd", 0.0)

    # ── 选择最佳 daily_trend（Langfuse 更全，PG 是备选）────────────────────
    daily_trend = lf_trend if lf_trend else pg_trend

    # ── 选择最佳 model_distribution ──────────────────────────────────────────
    model_distribution = lf_models if lf_models else pg_models

    return {
        "today": today_pg,
        "week":  week_pg,
        "model_distribution": model_distribution,
        "daily_trend":        daily_trend,
        "sources": {
            "langfuse_available": bool(lf_daily),
            "pg_records_today":   today_pg["requests"],
        },
    }
