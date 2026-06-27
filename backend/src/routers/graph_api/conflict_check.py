"""
POST /api/graph/conflict-check  — public conflict-check endpoint.

Detects Constraint nodes on the same Component that have contradicting values
across different Documents. Also writes CONFLICTS_WITH edges for each detected pair.

This is the non-admin counterpart to /api/admin/conflicts which provides
management UI functionality. This endpoint is intended for CI pipelines and
automated quality gates.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from ...auth.deps import get_current_user
from ...db.models import User
from ...services.graph.conflict_detection import (
    detect_constraint_conflicts,
    graph_health_summary,
    scan_dangling_references,
    detect_cycles_in_precedes,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.post("/conflict-check")
async def conflict_check(
    component: str | None = Query(default=None, description="零件编号（part_no），为空则扫描全图"),
    _: User = Depends(get_current_user),
) -> dict:
    """
    扫描约束冲突：同一 Component 在不同文档中的 Constraint 值存在矛盾时生成告警。

    - 差异率 > 10% 的数值型约束被判定为冲突。
    - 每对冲突自动在 Neo4j 中写入 `CONFLICTS_WITH` 关系边。
    - 无需管理员权限；适合在文档入库后由 CI 自动调用。

    示例调用：
        POST /api/graph/conflict-check?component=P-3042
    """
    conflicts = detect_constraint_conflicts(component_id=component)
    return {
        "component":      component or "*",
        "conflict_count": len(conflicts),
        "conflicts":      conflicts,
    }


@router.get("/conflict-check/health")
async def graph_health(
    _: User = Depends(get_current_user),
) -> dict:
    """
    图谱健康快照（6 项指标）：
    - health_score          0–100
    - isolated_nodes        无任何关系的 Section 节点数
    - dangling_references   REFERENCES 指向不存在文档的边数
    - constraint_coverage_pct 有 Constraint 的 Section 占比 (%)
    - conflict_count        当前 CONFLICTS_WITH 关系数
    - recent_7d_node_growth 近 7 天新增 Section 节点数
    - ingest_queue_length   Celery 入库队列积压
    """
    return graph_health_summary()


@router.get("/conflict-check/dangling")
async def dangling_refs(
    _: User = Depends(get_current_user),
) -> dict:
    """返回所有悬空引用：REFERENCES 边的目标文档不在图谱中。"""
    refs = scan_dangling_references()
    return {"count": len(refs), "items": refs}


@router.get("/conflict-check/cycles")
async def cycle_check(
    _: User = Depends(get_current_user),
) -> dict:
    """检测 PRECEDES 工序链中的循环依赖。"""
    cycles = detect_cycles_in_precedes()
    return {"cycle_count": len(cycles), "cycles": cycles}
