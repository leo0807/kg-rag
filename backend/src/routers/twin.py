"""
Digital Twin integration endpoint.

Receives anomaly events from digital twin platforms (Siemens Tecnomatix,
ANSYS Twin Builder) and returns relevant process specification guidance.

POST /api/twin/query
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/twin", tags=["digital-twin"])


class TwinAnomalyEvent(BaseModel):
    equipment_id: str = Field(..., description="设备编号")
    parameter: str = Field(..., description="异常参数名称，如'liquid_pressure'")
    current_value: float = Field(..., description="当前实际值")
    unit: str = Field("", description="单位，如'PSI'")
    component_id: str = Field("", description="相关零件号（可选）")
    simulation_id: str = Field("", description="仿真运行 ID（可选）")
    context: str = Field("", description="附加上下文信息")


class TwinQueryResponse(BaseModel):
    equipment_id: str
    parameter: str
    current_value: float
    unit: str
    compliance_status: str  # "compliant" | "violation" | "warning" | "unknown"
    violations: list[dict[str, Any]]
    relevant_sections: list[dict[str, Any]]
    recommendations: str
    simulation_result_stored: bool


@router.post("/query", response_model=TwinQueryResponse)
async def twin_query(event: TwinAnomalyEvent) -> TwinQueryResponse:
    """
    Receive digital twin anomaly event and return process specification guidance.
    Also stores simulation result in knowledge graph.
    """
    import asyncio
    from ..core.database import get_driver
    from ..services.graph.conflict_detection import detect_constraint_conflicts

    # 1. Find relevant constraints in knowledge graph
    driver = get_driver()

    def _get_specs():
        with driver.session() as s:
            result = s.run(
                """
                MATCH (c:Constraint)<-[:HAS_CONSTRAINT]-(sec:Section)
                WHERE c.parameter CONTAINS $param
                  AND ($unit = '' OR c.unit = $unit)
                OPTIONAL MATCH (d:Document {name: sec.doc_id})
                RETURN c.parameter AS parameter, c.value AS spec_value,
                       c.min AS min_val, c.max AS max_val, c.unit AS unit,
                       sec.chunk_id AS section_id, sec.title AS section_title,
                       sec.doc_id AS doc_id
                LIMIT 10
                """,
                param=event.parameter, unit=event.unit,
            )
            return [dict(r) for r in result]

    specs = await asyncio.to_thread(_get_specs)

    # 2. Evaluate compliance
    violations = []
    for spec in specs:
        min_v = float(spec["min_val"]) if spec.get("min_val") is not None else None
        max_v = float(spec["max_val"]) if spec.get("max_val") is not None else None
        spec_v_str = spec.get("spec_value", "")
        if min_v is None and max_v is None and spec_v_str:
            try:
                sv = float(spec_v_str)
                min_v, max_v = sv * 0.9, sv * 1.1
            except ValueError:
                pass
        violated = False
        if min_v is not None and event.current_value < min_v:
            violations.append({
                "type": "below_minimum",
                "spec_min": min_v,
                "actual": event.current_value,
                "unit": spec.get("unit", event.unit),
                "source": f"{spec['doc_id']} — {spec['section_title']}",
                "section_id": spec["section_id"],
            })
            violated = True
        elif max_v is not None and event.current_value > max_v:
            violations.append({
                "type": "exceeds_maximum",
                "spec_max": max_v,
                "actual": event.current_value,
                "unit": spec.get("unit", event.unit),
                "source": f"{spec['doc_id']} — {spec['section_title']}",
                "section_id": spec["section_id"],
            })
            violated = True

    compliance_status = (
        "violation" if violations
        else ("compliant" if specs else "unknown")
    )

    # 3. Build recommendations
    if violations:
        violation_text = "; ".join(
            f"{v['type']} (actual={v['actual']}, limit={v.get('spec_min') or v.get('spec_max')} {v['unit']})"
            for v in violations[:3]
        )
        recommendations = (
            f"检测到 {len(violations)} 项约束违规：{violation_text}。"
            "请参考相关规范章节，立即停止操作并进行参数调整。"
        )
    elif specs:
        recommendations = f"参数 {event.parameter} 当前值 {event.current_value} {event.unit} 在规范范围内。"
    else:
        recommendations = f"未找到参数 {event.parameter} 的规范约束，请联系文档管理员。"

    # 4. Store simulation result in graph
    simulation_stored = False
    if event.simulation_id:
        def _store():
            with driver.session() as s:
                s.run(
                    """
                    MERGE (sr:SimulationResult {sim_id: $sim_id})
                    SET sr.equipment_id = $equip, sr.parameter = $param,
                        sr.actual_value = $val, sr.unit = $unit,
                        sr.pass = $pass, sr.violation_count = $vc
                    """,
                    sim_id=event.simulation_id,
                    equip=event.equipment_id,
                    param=event.parameter,
                    val=event.current_value,
                    unit=event.unit,
                    **{"pass": len(violations) == 0, "vc": len(violations)},
                )
        await asyncio.to_thread(_store)
        simulation_stored = True

    relevant_sections = [
        {
            "section_id": s["section_id"],
            "title": s["section_title"],
            "doc_id": s["doc_id"],
        }
        for s in specs[:5]
    ]

    return TwinQueryResponse(
        equipment_id=event.equipment_id,
        parameter=event.parameter,
        current_value=event.current_value,
        unit=event.unit,
        compliance_status=compliance_status,
        violations=violations,
        relevant_sections=relevant_sections,
        recommendations=recommendations,
        simulation_result_stored=simulation_stored,
    )


@router.get("/simulation-results/{equipment_id}")
async def get_simulation_results(equipment_id: str, limit: int = 20):
    """Return recent simulation results for a piece of equipment."""
    import asyncio
    from ..core.database import get_driver
    driver = get_driver()

    def _run():
        with driver.session() as s:
            result = s.run(
                """
                MATCH (sr:SimulationResult {equipment_id: $equip})
                RETURN sr.sim_id AS sim_id, sr.parameter AS parameter,
                       sr.actual_value AS actual_value, sr.unit AS unit,
                       sr.pass AS passed, sr.violation_count AS violations
                ORDER BY sr.sim_id DESC
                LIMIT $limit
                """,
                equip=equipment_id, limit=limit,
            )
            return [dict(r) for r in result]

    return await asyncio.to_thread(_run)
