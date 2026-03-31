"""
src/routers/admin.py
管理员专用 API：实体审核、配置热重载
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from pydantic import BaseModel
from ..core.database import get_driver
from ..auth.deps import get_current_user
from ..db.models import User

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

    since = datetime.now(timezone.utc) - timedelta(days=days)

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
