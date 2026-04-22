"""
src/routers/admin_dashboard.py
管理员专用 API：治理驾驶舱（图谱指标、查询热词、治理建议）
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from neo4j import Driver
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_driver
from ...db.session import get_db, AsyncSessionLocal
from ...db.models import LLMUsage, User
from ..feedback import QueryFeedback
from .entities import _require_admin
from ...services.parsing.validator import validate_all

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/dashboard", tags=["admin"])

@router.get("/stats")
async def get_dashboard_stats(
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """获取图谱健康度与活跃度统计"""
    
    # 1. 图谱健康度 (Neo4j)
    with driver.session() as session:
        # 基础统计
        basic_res = session.run("""
            MATCH (n) WITH count(n) AS node_count
            MATCH ()-[r]->() WITH node_count, count(r) AS rel_count
            RETURN node_count, rel_count
        """).single()
        
        # 孤立节点 (没有出边也没有入边)
        orphan_res = session.run("""
            MATCH (n)
            WHERE NOT (n)--()
            RETURN count(n) AS orphan_count
        """).single()
        
        node_count = basic_res["node_count"]
        rel_count = basic_res["rel_count"]
        orphan_count = orphan_res["orphan_count"]
        
        density = rel_count / (node_count * (node_count - 1)) if node_count > 1 else 0
        orphan_ratio = orphan_count / node_count if node_count > 0 else 0

    # 2. 近期活跃度 (SQL)
    since = datetime.utcnow() - timedelta(days=7)
    usage_res = await db.execute(
        select(func.count(LLMUsage.id)).where(LLMUsage.created_at >= since)
    )
    queries_7d = usage_res.scalar()

    return {
        "graph": {
            "node_count": node_count,
            "rel_count": rel_count,
            "orphan_count": orphan_count,
            "orphan_ratio": round(orphan_ratio, 4),
            "density": round(density, 6),
        },
        "activity": {
            "queries_7d": queries_7d,
        }
    }

@router.get("/wordcloud")
async def get_query_wordcloud(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """获取用户查询热词云"""
    # 获取最近 1000 条查询
    result = await db.execute(
        select(LLMUsage.question_preview)
        .order_by(desc(LLMUsage.created_at))
        .limit(1000)
    )
    questions = result.scalars().all()
    
    # 简单的分词聚合逻辑（如果有 jieba 可以用更专业的）
    words_map = {}
    stop_words = {"什么", "如何", "怎么", "的", "在", "是", "了", "哪些", "要求", "规定"}
    
    import re
    for q in questions:
        if not q: continue
        # 提取中文、英文、数字
        tokens = re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]+', q)
        for t in tokens:
            if t in stop_words: continue
            words_map[t] = words_map.get(t, 0) + 1
            
    sorted_words = sorted(words_map.items(), key=lambda x: -x[1])
    return [{"text": k, "value": v} for k, v in sorted_words[:limit]]

@router.get("/suggestions")
async def get_governance_suggestions(
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """获取治理建议池（质量问题文档 + 负面反馈）"""
    
    # 1. 解析质量问题 (来自 validator)
    v_report = validate_all(driver)
    problem_docs = [
        d for d in v_report.get("documents", [])
        if not d["valid"] or d["score"] < 70
    ]
    
    # 2. 负面反馈 (来自 QueryFeedback)
    feedback_res = await db.execute(
        select(QueryFeedback)
        .where(QueryFeedback.rating == -1)
        .order_by(desc(QueryFeedback.created_at))
        .limit(20)
    )
    neg_feedbacks = [
        {
            "id": f["id"],
            "question": f["question"],
            "answer": f["answer"][:100] + "...",
            "created_at": f["created_at"].isoformat()
        }
        for f in [row[0].__dict__ for row in feedback_res.all()]
    ]

    return {
        "low_quality_documents": problem_docs[:10],
        "negative_feedbacks": neg_feedbacks,
        "summary": {
            "total_issues": len(problem_docs) + len(neg_feedbacks),
            "avg_graph_score": v_report.get("avg_score", 0)
        }
    }
