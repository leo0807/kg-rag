"""
src/routers/admin.py
管理员专用 API：实体审核、配置热重载、用户活跃度报表
"""
import csv
import io
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from neo4j import Driver
from pydantic import BaseModel
from sqlalchemy import select, func
from ..core.database import get_driver
from ..auth.deps import get_current_user
from ..db.models import User
from ..db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return user


# ── 实体管理 ──────────────────────────────────────────────────────────────────

class MergeRequest(BaseModel):
    source_names: list[str]   # 要合并掉的节点名称列表
    target_name:  str         # 合并目标（保留）
    type:         str         # Tool | Material | Process


@router.delete("/entities/{name}")
async def delete_entity(
    name: str,
    type: str = "Tool",
    driver: Driver = Depends(get_driver),
    _: User = Depends(_require_admin),
):
    """删除指定实体节点（含所有关系）"""
    valid_types = {"Tool", "Material", "Process"}
    if type not in valid_types:
        raise HTTPException(400, f"type 必须是 Tool/Material/Process，收到: {type}")

    with driver.session() as session:
        result = session.run(
            f"MATCH (e:{type} {{name: $name}}) RETURN count(e) AS cnt",
            name=name
        ).single()
        if not result or result["cnt"] == 0:
            raise HTTPException(404, f"实体不存在: {name}")

        session.run(f"MATCH (e:{type} {{name: $name}}) DETACH DELETE e", name=name)

    logger.info("管理员删除实体: %s (%s)", name, type)
    return {"status": "deleted", "name": name, "type": type}


@router.post("/entities/merge")
async def merge_entities(
    req: MergeRequest,
    driver: Driver = Depends(get_driver),
    _: User = Depends(_require_admin),
):
    """
    将多个源实体合并到目标实体。
    所有源节点的关系迁移到目标节点后删除源节点。
    """
    valid_types = {"Tool", "Material", "Process"}
    if req.type not in valid_types:
        raise HTTPException(400, f"type 必须是 Tool/Material/Process")

    merged_count = 0
    with driver.session() as session:
        # 确保目标节点存在
        session.run(f"MERGE (keep:{req.type} {{name: $name}})", name=req.target_name)

        for src_name in req.source_names:
            if src_name == req.target_name:
                continue

            # 将源节点的出边迁移到目标节点
            session.run(f"""
                MATCH (src:{req.type} {{name: $src}})
                MATCH (keep:{req.type} {{name: $keep}})
                OPTIONAL MATCH (src)-[r]->(tgt)
                WHERE tgt <> keep
                WITH keep, type(r) AS rel_type, tgt
                CALL apoc.merge.relationship(keep, rel_type, {{}}, {{}}, tgt, {{}}) YIELD rel
                RETURN count(rel)
            """, src=src_name, keep=req.target_name)

            # 将源节点的入边迁移到目标节点（使用基础 Cypher 替代 APOC）
            # 获取入边并用基础 Cypher 创建
            in_result = session.run(f"""
                MATCH (origin)-[r]->(src:{req.type} {{name: $src}})
                RETURN elementId(origin) AS origin_id, type(r) AS rel_type
            """, src=src_name)
            in_edges = [(r["origin_id"], r["rel_type"]) for r in in_result]
            for origin_id, rel_type in in_edges:
                session.run(f"""
                    MATCH (origin) WHERE elementId(origin) = $oid
                    MATCH (keep:{req.type} {{name: $keep}})
                    MERGE (origin)-[:{rel_type}]->(keep)
                """, oid=origin_id, keep=req.target_name)

            # 删除源节点
            session.run(f"MATCH (e:{req.type} {{name: $src}}) DETACH DELETE e", src=src_name)
            merged_count += 1

    logger.info("管理员合并实体: %s → %s, 合并 %d 个", req.source_names, req.target_name, merged_count)
    return {
        "status":  "merged",
        "target":  req.target_name,
        "merged":  merged_count,
        "sources": req.source_names,
    }


# ── 配置热重载 ─────────────────────────────────────────────────────────────────

@router.post("/reload-config")
async def reload_config(_: User = Depends(_require_admin)):
    """
    热重载配置：清除 lru_cache，下一次调用 get_settings() 将重新读取 .env 文件。
    注意：模块级 settings 变量不会立即更新，需重启服务才能完全生效。
    """
    from ..core.config import get_settings
    get_settings.cache_clear()
    return {"status": "ok", "message": "配置缓存已清除，下次调用 get_settings() 将重新加载"}


# ── LLM 成本报表 ───────────────────────────────────────────────────────────────

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
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, func, text
    from ..db.session import AsyncSessionLocal
    from ..db.models import LLMUsage

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


# ── 用户活跃度报表 ─────────────────────────────────────────────────────────────

async def _build_activity_report(days: int) -> dict:
    """构建用户活跃度报表数据（内部复用函数）"""
    from ..db.models import LLMUsage, Conversation, User as UserModel

    # PostgreSQL stores TIMESTAMP WITHOUT TIME ZONE — pass naive datetimes
    since = datetime.utcnow() - timedelta(days=days)
    until = datetime.utcnow()
    weeks = max(days / 7, 1)

    async with AsyncSessionLocal() as db:
        # ── 所有启用用户 ────────────────────────────────────────────────
        users_result = await db.execute(
            select(UserModel).where(UserModel.is_active == True)
        )
        all_users: dict[str, UserModel] = {u.id: u for u in users_result.scalars().all()}

        # ── LLMUsage：每用户活跃天数 / 总查询数 / 最后活跃时间 ──────────
        usage_result = await db.execute(
            select(
                LLMUsage.user_id,
                func.count(func.distinct(func.date(LLMUsage.created_at))).label("active_days"),
                func.count(LLMUsage.id).label("total_queries"),
                func.max(LLMUsage.created_at).label("last_active"),
            )
            .where(LLMUsage.created_at >= since)
            .where(LLMUsage.user_id.isnot(None))
            .group_by(LLMUsage.user_id)
        )
        usage_by_user = {r.user_id: r for r in usage_result.all()}

        # ── LLMUsage：每用户最常用策略 ──────────────────────────────────
        strategy_result = await db.execute(
            select(
                LLMUsage.user_id,
                LLMUsage.strategy,
                func.count(LLMUsage.id).label("cnt"),
            )
            .where(LLMUsage.created_at >= since)
            .where(LLMUsage.user_id.isnot(None))
            .where(LLMUsage.strategy != "")
            .group_by(LLMUsage.user_id, LLMUsage.strategy)
        )
        strategy_counts: dict[str, dict[str, int]] = defaultdict(dict)
        for row in strategy_result.all():
            strategy_counts[row.user_id][row.strategy] = int(row.cnt)
        top_strategy: dict[str, str] = {
            uid: max(counts, key=lambda k: counts[k])
            for uid, counts in strategy_counts.items()
        }

        # ── Conversations：每用户对话数 ──────────────────────────────────
        conv_result = await db.execute(
            select(
                Conversation.user_id,
                func.count(Conversation.id).label("total_conversations"),
            )
            .where(Conversation.created_at >= since)
            .group_by(Conversation.user_id)
        )
        conv_by_user: dict[str, int] = {r.user_id: int(r.total_conversations) for r in conv_result.all()}

        # ── DAU 时序：每天活跃用户数 + 查询数 ───────────────────────────
        dau_result = await db.execute(
            select(
                func.date(LLMUsage.created_at).label("day"),
                func.count(func.distinct(LLMUsage.user_id)).label("active_users"),
                func.count(LLMUsage.id).label("queries"),
            )
            .where(LLMUsage.created_at >= since)
            .where(LLMUsage.user_id.isnot(None))
            .group_by(func.date(LLMUsage.created_at))
            .order_by(func.date(LLMUsage.created_at))
        )
        dau_series = [
            {"date": str(r.day), "active_users": int(r.active_users), "queries": int(r.queries)}
            for r in dau_result.all()
        ]

    # ── 拼装每用户行 ─────────────────────────────────────────────────────
    active_uids = set(usage_by_user) | set(conv_by_user)
    user_rows: list[dict] = []

    for uid in active_uids:
        u        = all_users.get(uid)
        usage    = usage_by_user.get(uid)
        total_q  = int(usage.total_queries) if usage else 0
        total_c  = conv_by_user.get(uid, 0)

        user_rows.append({
            "user_id":               uid,
            "username":              u.username  if u else uid[:8],
            "full_name":             u.full_name if u else "",
            "department":            u.department if u else "",
            "active_days":           int(usage.active_days) if usage else 0,
            "total_queries":         total_q,
            "weekly_queries":        round(total_q / weeks, 1),
            "total_conversations":   total_c,
            "avg_turns_per_session": round(total_q / total_c, 1) if total_c else None,
            "top_strategy":          top_strategy.get(uid, "—"),
            "last_active":           usage.last_active.isoformat() if usage and usage.last_active else None,
        })

    user_rows.sort(key=lambda x: x["total_queries"], reverse=True)

    # ── 按部门聚合 ───────────────────────────────────────────────────────
    dept_acc: dict[str, dict] = {}
    for row in user_rows:
        dept = row["department"] or "未知部门"
        if dept not in dept_acc:
            dept_acc[dept] = {
                "department":     dept,
                "user_count":     0,
                "active_days_sum": 0,
                "total_queries":  0,
                "total_conversations": 0,
                "strategy_counts": defaultdict(int),
            }
        d = dept_acc[dept]
        d["user_count"]          += 1
        d["active_days_sum"]     += row["active_days"]
        d["total_queries"]       += row["total_queries"]
        d["total_conversations"] += row["total_conversations"]
        if row["top_strategy"] != "—":
            d["strategy_counts"][row["top_strategy"]] += 1

    dept_rows = []
    for dept, d in dept_acc.items():
        tq = d["total_queries"]
        tc = d["total_conversations"]
        top_s = max(d["strategy_counts"], key=lambda k: d["strategy_counts"][k]) \
                if d["strategy_counts"] else "—"
        dept_rows.append({
            "department":            dept,
            "user_count":            d["user_count"],
            "avg_active_days":       round(d["active_days_sum"] / max(d["user_count"], 1), 1),
            "total_queries":         tq,
            "weekly_queries":        round(tq / weeks, 1),
            "total_conversations":   tc,
            "avg_turns_per_session": round(tq / tc, 1) if tc else None,
            "top_strategy":          top_s,
        })
    dept_rows.sort(key=lambda x: x["total_queries"], reverse=True)

    # ── 汇总 ─────────────────────────────────────────────────────────────
    total_q = sum(r["total_queries"] for r in user_rows)
    total_c = sum(r["total_conversations"] for r in user_rows)
    avg_dau = round(
        sum(d["active_users"] for d in dau_series) / max(len(dau_series), 1), 1
    ) if dau_series else 0.0

    return {
        "period":  {"days": days, "since": since.isoformat(), "until": until.isoformat()},
        "summary": {
            "total_active_users":     len(user_rows),
            "total_queries":          total_q,
            "total_conversations":    total_c,
            "avg_turns_per_session":  round(total_q / total_c, 1) if total_c else None,
            "avg_daily_active_users": avg_dau,
        },
        "by_user":       user_rows,
        "by_department": dept_rows,
        "dau":           dau_series,
    }


@router.get("/analytics/user-activity")
async def user_activity_report(
    days: int = 30,
    _: User = Depends(_require_admin),
):
    """
    用户活跃度报表：DAU、周查询量、平均会话轮数、最常用检索策略。
    支持按用户和按部门两个维度，含每日活跃用户时序数据。
    """
    return await _build_activity_report(days)


@router.get("/analytics/user-activity/csv")
async def user_activity_csv(
    days: int = 30,
    _: User = Depends(_require_admin),
):
    """导出用户活跃度报表为 CSV（适配 Metabase / Superset BI 工具）"""
    report = await _build_activity_report(days)

    buf = io.StringIO()
    writer = csv.writer(buf)

    # 按用户明细
    writer.writerow([
        "user_id", "username", "full_name", "department",
        "active_days", "total_queries", "weekly_queries",
        "total_conversations", "avg_turns_per_session",
        "top_strategy", "last_active",
    ])
    for row in report["by_user"]:
        writer.writerow([
            row["user_id"],     row["username"],    row["full_name"],
            row["department"],  row["active_days"],  row["total_queries"],
            row["weekly_queries"], row["total_conversations"],
            row["avg_turns_per_session"] or "",
            row["top_strategy"], row["last_active"] or "",
        ])

    writer.writerow([])
    writer.writerow(["# 按部门汇总"])
    writer.writerow([
        "department", "user_count", "avg_active_days",
        "total_queries", "weekly_queries", "total_conversations",
        "avg_turns_per_session", "top_strategy",
    ])
    for row in report["by_department"]:
        writer.writerow([
            row["department"],   row["user_count"],   row["avg_active_days"],
            row["total_queries"], row["weekly_queries"], row["total_conversations"],
            row["avg_turns_per_session"] or "", row["top_strategy"],
        ])

    writer.writerow([])
    writer.writerow(["# 每日活跃用户 (DAU)"])
    writer.writerow(["date", "active_users", "queries"])
    for row in report["dau"]:
        writer.writerow([row["date"], row["active_users"], row["queries"]])

    since_str = report["period"]["since"][:10]
    filename  = f"user_activity_{since_str}_d{days}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
