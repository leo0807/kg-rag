"""
src/routers/admin_analytics.py
管理员专用 API：LLM 成本报表、热点节点、检索策略效果对比
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from .entities import _require_admin
from ...db.models import User
from ...db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

_STRATEGY_LABEL: dict[str, str] = {
    "parallel":        "并行检索",
    "sequential":      "顺序检索",
    "graph_augmented": "图谱增强",
    "multi_hop":       "多跳推理",
    "gnn":             "GNN 检索",
}


@router.get("/llm-costs")
async def llm_cost_report(
    days:       int  = 30,
    group_by:   str  = "user",    # user | department | model | day
    _: User = Depends(_require_admin),
):
    """
    查询最近 N 天的 LLM 用量与费用汇总。
    group_by: user（按用户）| department（按部门）| model（按模型）| day（按天）
    """
    from ...db.models import LLMUsage

    since = datetime.utcnow() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        # ── 汇总表（按指定维度）──────────────────────────────────────────────
        if group_by == "department":
            group_col = LLMUsage.department
        elif group_by == "model":
            group_col = LLMUsage.model
        elif group_by == "day":
            group_col = func.date(LLMUsage.created_at)
        else:  # default: user
            group_col = LLMUsage.user_id

        result = await db.execute(
            select(
                group_col.label("group_key"),
                func.sum(LLMUsage.prompt_tokens).label("prompt_tokens"),
                func.sum(LLMUsage.completion_tokens).label("completion_tokens"),
                func.sum(LLMUsage.cost_usd).label("cost_usd"),
                func.count(LLMUsage.id).label("call_count"),
            )
            .where(LLMUsage.created_at >= since)
            .group_by(group_col)
            .order_by(func.sum(LLMUsage.cost_usd).desc())
        )
        rows = result.all()

        # ── 总计 ────────────────────────────────────────────────────────────
        total_result = await db.execute(
            select(
                func.sum(LLMUsage.prompt_tokens).label("prompt_tokens"),
                func.sum(LLMUsage.completion_tokens).label("completion_tokens"),
                func.sum(LLMUsage.cost_usd).label("cost_usd"),
                func.count(LLMUsage.id).label("call_count"),
            ).where(LLMUsage.created_at >= since)
        )
        total = total_result.one()

    CNY_RATE = 7.25
    breakdown = [
        {
            "key":               str(r.group_key or "anonymous"),
            "prompt_tokens":     int(r.prompt_tokens or 0),
            "completion_tokens": int(r.completion_tokens or 0),
            "total_tokens":      int((r.prompt_tokens or 0) + (r.completion_tokens or 0)),
            "cost_usd":          round(float(r.cost_usd or 0), 6),
            "cost_cny":          round(float(r.cost_usd or 0) * CNY_RATE, 4),
            "call_count":        int(r.call_count or 0),
        }
        for r in rows
    ]

    return {
        "days":     days,
        "group_by": group_by,
        "since":    since.isoformat(),
        "total": {
            "prompt_tokens":     int(total.prompt_tokens or 0),
            "completion_tokens": int(total.completion_tokens or 0),
            "total_tokens":      int((total.prompt_tokens or 0) + (total.completion_tokens or 0)),
            "cost_usd":          round(float(total.cost_usd or 0), 6),
            "cost_cny":          round(float(total.cost_usd or 0) * CNY_RATE, 4),
            "call_count":        int(total.call_count or 0),
        },
        "breakdown": breakdown,
    }


@router.get("/analytics/hot-nodes")
async def hot_nodes_report(
    top_k: int = 20,
    days:  int = 30,
    _: User = Depends(_require_admin),
):
    """
    查询热点 Section 节点排行。
    热力值 = 被引用次数 + 被点击次数 × 3（点击信号权重更高）。
    数据来源：query_feedback 表的 sources 字段 + clicked_source 详情事件。
    """
    import json as _json
    from ...routers.feedback import QueryFeedback

    since = datetime.utcnow() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(QueryFeedback.sources, QueryFeedback.detail)
            .where(QueryFeedback.created_at >= since)
        )
        rows = result.all()

    cited:   dict[str, int]  = {}
    clicked: dict[str, int]  = {}
    meta:    dict[str, dict] = {}   # chunk_id → {doc_id, title, number}

    for sources_json, detail in rows:
        try:
            sources = _json.loads(sources_json or "[]")
            for s in sources:
                cid = s.get("chunk_id")
                if not cid:
                    continue
                cited[cid] = cited.get(cid, 0) + 1
                if cid not in meta:
                    meta[cid] = {
                        "doc_id": s.get("doc_id", ""),
                        "title":  s.get("title",  ""),
                        "number": s.get("number", ""),
                    }
        except Exception:
            pass
        if detail and detail.startswith("clicked_source:"):
            cid = detail[len("clicked_source:"):]
            if cid:
                clicked[cid] = clicked.get(cid, 0) + 1

    all_ids = set(cited) | set(clicked)
    if not all_ids:
        return {
            "period": {"days": days, "since": since.isoformat()},
            "nodes":  [],
        }

    heat: dict[str, float] = {
        cid: cited.get(cid, 0) + clicked.get(cid, 0) * 3.0
        for cid in all_ids
    }
    max_heat = max(heat.values())
    ranked = sorted(all_ids, key=lambda k: heat[k], reverse=True)[:top_k]

    nodes = []
    for rank, cid in enumerate(ranked, start=1):
        m = meta.get(cid, {})
        nodes.append({
            "rank":          rank,
            "chunk_id":      cid,
            "doc_id":        m.get("doc_id", ""),
            "title":         m.get("title",  ""),
            "number":        m.get("number", ""),
            "cited_count":   cited.get(cid, 0),
            "clicked_count": clicked.get(cid, 0),
            "heat_score":    round(heat[cid], 2),
            "heat_norm":     round(heat[cid] / max_heat, 4),
        })

    return {
        "period": {"days": days, "since": since.isoformat()},
        "nodes":  nodes,
    }


@router.get("/analytics/strategy-stats")
async def strategy_stats(
    days: int = 30,
    _: User = Depends(_require_admin),
):
    """
    检索策略效果对比报表（管理员）。
    数据来源：
      - LLMUsage    → 延迟（ms）、token 消耗、调用次数
      - QueryFeedback → 👍 好评率、平均返回来源数
    辅助调整"自动策略选择"的路由规则。
    """
    import json as _json
    from ...db.models import LLMUsage
    from ...routers.feedback import QueryFeedback

    since = datetime.utcnow() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        # ── LLMUsage：延迟 / token / 费用（按策略聚合）─────────────────
        usage_result = await db.execute(
            select(
                LLMUsage.strategy,
                func.count(LLMUsage.id).label("call_count"),
                func.avg(LLMUsage.latency_ms).label("avg_latency_ms"),
                func.avg(LLMUsage.prompt_tokens + LLMUsage.completion_tokens).label("avg_tokens"),
                func.sum(LLMUsage.prompt_tokens + LLMUsage.completion_tokens).label("total_tokens"),
                func.avg(LLMUsage.cost_usd).label("avg_cost_usd"),
                func.sum(LLMUsage.cost_usd).label("total_cost_usd"),
            )
            .where(LLMUsage.created_at >= since)
            .where(LLMUsage.strategy != "")
            .group_by(LLMUsage.strategy)
        )
        usage_by_strategy = {r.strategy: r for r in usage_result.all()}

        # ── QueryFeedback：评分 + 来源数（按策略聚合，Python 侧计算）───
        fb_result = await db.execute(
            select(
                QueryFeedback.strategy,
                QueryFeedback.rating,
                QueryFeedback.sources,
            )
            .where(QueryFeedback.created_at >= since)
        )
        fb_rows = fb_result.all()

    # 在 Python 侧聚合 feedback
    fb_agg: dict[str, dict] = {}
    for strategy, rating, sources_json in fb_rows:
        key = strategy or "parallel"
        if key not in fb_agg:
            fb_agg[key] = {"positive": 0, "negative": 0, "explicit": 0, "src_counts": []}
        agg = fb_agg[key]
        if rating == 1:
            agg["positive"] += 1
            agg["explicit"] += 1
        elif rating == -1:
            agg["negative"] += 1
            agg["explicit"] += 1
        try:
            srcs = _json.loads(sources_json or "[]")
            if isinstance(srcs, list):
                agg["src_counts"].append(len(srcs))
        except Exception:
            pass

    all_strategies = set(usage_by_strategy) | set(fb_agg)
    rows: list[dict] = []

    for strategy in sorted(all_strategies):
        u   = usage_by_strategy.get(strategy)
        fb  = fb_agg.get(strategy, {})
        explicit    = fb.get("explicit", 0)
        positive    = fb.get("positive", 0)
        src_counts  = fb.get("src_counts", [])

        rows.append({
            "strategy":         strategy,
            "label":            _STRATEGY_LABEL.get(strategy, strategy),
            "call_count":       int(u.call_count) if u else 0,
            "avg_latency_ms":   round(float(u.avg_latency_ms)) if u and u.avg_latency_ms else None,
            "avg_tokens":       round(float(u.avg_tokens)) if u and u.avg_tokens else None,
            "total_tokens":     int(u.total_tokens) if u and u.total_tokens else 0,
            "avg_cost_usd":     round(float(u.avg_cost_usd), 6) if u and u.avg_cost_usd else None,
            "total_cost_usd":   round(float(u.total_cost_usd), 4) if u and u.total_cost_usd else 0.0,
            "explicit_ratings": explicit,
            "positive_count":   positive,
            "negative_count":   fb.get("negative", 0),
            "positive_rate":    round(positive / explicit, 4) if explicit > 0 else None,
            "feedback_count":   len(src_counts),
            "avg_source_count": round(sum(src_counts) / len(src_counts), 1) if src_counts else None,
        })

    rows.sort(key=lambda x: x["call_count"], reverse=True)

    return {
        "period":     {"days": days, "since": since.isoformat()},
        "strategies": rows,
    }


@router.get("/analytics/empty-queries")
async def empty_queries_report(
    days:  int = Query(7,  ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
    _: User = Depends(_require_admin),
):
    """
    返回最近 N 天 sources_count=0 的查询词频统计。
    用于识别知识盲区，指导下一批 PDF 入库优先级。
    """
    from ...routers.feedback import QueryFeedback

    cutoff = datetime.utcnow() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        stmt = (
            select(
                QueryFeedback.question,
                func.count(QueryFeedback.id).label("count"),
                func.max(QueryFeedback.created_at).label("last_seen"),
            )
            .where(
                QueryFeedback.sources_count == 0,
                QueryFeedback.created_at >= cutoff,
            )
            .group_by(QueryFeedback.question)
            .order_by(func.count(QueryFeedback.id).desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()

    return {
        "days":         days,
        "total_unique": len(rows),
        "items": [
            {
                "question": r.question,
                "count":    r.count,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in rows
        ],
    }
