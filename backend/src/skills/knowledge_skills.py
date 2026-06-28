"""
Agent Skills — domain-specific structured tools for LLM ReAct agents.
Each skill is a standalone async function callable from LangGraph agents.
Compatible with OpenAI Function Calling / Anthropic Tool Use format.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)

# ─── Skill definitions (OpenAI/Anthropic tool_use compatible) ────────────────

SKILL_DEFINITIONS: list[dict] = [
    {
        "name": "query_procedure",
        "description": "查询特定工艺步骤的详细要求和约束条件",
        "parameters": {
            "type": "object",
            "properties": {
                "procedure_name": {
                    "type": "string",
                    "description": "工艺名称，如'液压管路安装'",
                },
                "aspect": {
                    "type": "string",
                    "enum": ["steps", "tools", "materials", "constraints", "safety"],
                    "description": "关注维度",
                },
                "doc_id": {
                    "type": "string",
                    "description": "限定搜索的文档 ID（可选）",
                },
            },
            "required": ["procedure_name"],
        },
    },
    {
        "name": "check_compliance",
        "description": "检查某工艺参数是否满足规范约束（如力矩值是否在允许范围内）",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter": {"type": "string", "description": "参数名称（如'安装力矩'）"},
                "value": {"type": "number", "description": "实际值"},
                "unit": {"type": "string", "description": "单位（如'N·m'）"},
                "component": {"type": "string", "description": "零件号（可选）"},
            },
            "required": ["parameter", "value", "unit"],
        },
    },
    {
        "name": "find_related_specs",
        "description": "沿图谱 REFERENCES 关系查找与某规范相关联的上下游文档",
        "parameters": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "文档编号"},
                "direction": {
                    "type": "string",
                    "enum": ["upstream", "downstream", "both"],
                    "default": "both",
                },
                "depth": {"type": "integer", "default": 2, "minimum": 1, "maximum": 5},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "trace_change_history",
        "description": "查询某章节的历史版本变更记录",
        "parameters": {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "section_number": {"type": "string"},
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "get_hazards",
        "description": "获取某工艺或章节涉及的危险源清单",
        "parameters": {
            "type": "object",
            "properties": {
                "procedure_name": {"type": "string"},
                "doc_id": {"type": "string"},
            },
        },
    },
    {
        "name": "get_inspection_requirements",
        "description": "获取某工序的质量检验要求（检验方法、频率、验收标准）",
        "parameters": {
            "type": "object",
            "properties": {
                "procedure_name": {"type": "string"},
                "doc_id": {"type": "string"},
            },
        },
    },
]


# ─── Skill implementations ────────────────────────────────────────────────────

async def query_procedure(procedure_name: str, aspect: str = "steps",
                           doc_id: str | None = None) -> dict[str, Any]:
    from ..core.database import get_driver
    driver = get_driver()

    def _run():
        with driver.session() as s:
            doc_filter = "AND s.doc_id = $doc_id" if doc_id else ""
            result = s.run(
                f"""
                MATCH (s:Section)
                WHERE (s.content CONTAINS $name OR s.title CONTAINS $name)
                {doc_filter}
                OPTIONAL MATCH (s)-[:REQUIRES_TOOL]->(t:Tool)
                OPTIONAL MATCH (s)-[:USES_MATERIAL]->(m:Material)
                OPTIONAL MATCH (s)-[:HAS_CONSTRAINT]->(c:Constraint)
                OPTIONAL MATCH (s)-[:WARNS_OF]->(h:Hazard)
                RETURN s.chunk_id AS chunk_id, s.title AS title,
                       s.doc_id AS doc_id, s.content AS content,
                       collect(DISTINCT t.name) AS tools,
                       collect(DISTINCT m.name) AS materials,
                       collect(DISTINCT {{parameter: c.parameter, value: c.value, unit: c.unit}}) AS constraints,
                       collect(DISTINCT h.description) AS hazards
                LIMIT 5
                """,
                name=procedure_name,
                **({"doc_id": doc_id} if doc_id else {}),
            )
            rows = [dict(r) for r in result]
            if not rows:
                return {"found": False, "procedure_name": procedure_name}

            row = rows[0]
            if aspect == "tools":
                return {"tools": row["tools"], "section": row["title"]}
            elif aspect == "materials":
                return {"materials": row["materials"], "section": row["title"]}
            elif aspect == "constraints":
                return {"constraints": [c for c in row["constraints"] if c.get("parameter")],
                        "section": row["title"]}
            elif aspect == "safety":
                return {"hazards": row["hazards"], "section": row["title"]}
            else:  # steps
                return {
                    "title": row["title"],
                    "doc_id": row["doc_id"],
                    "content_excerpt": (row["content"] or "")[:600],
                }

    return await asyncio.to_thread(_run)


async def check_compliance(parameter: str, value: float, unit: str,
                            component: str | None = None) -> dict[str, Any]:
    from ..core.database import get_driver
    driver = get_driver()

    def _run():
        with driver.session() as s:
            result = s.run(
                """
                MATCH (c:Constraint)
                WHERE c.parameter CONTAINS $param AND c.unit = $unit
                OPTIONAL MATCH (sec:Section)-[:HAS_CONSTRAINT]->(c)
                RETURN c.parameter AS parameter, c.value AS spec_value,
                       c.unit AS unit, c.min AS min_val, c.max AS max_val,
                       sec.title AS section, sec.doc_id AS doc_id
                LIMIT 5
                """,
                param=parameter, unit=unit,
            )
            specs = [dict(r) for r in result]

        if not specs:
            return {"compliant": None, "message": f"No constraint found for {parameter} ({unit})"}

        violations = []
        for spec in specs:
            min_v = spec.get("min_val")
            max_v = spec.get("max_val")
            spec_v = spec.get("spec_value")
            if min_v is not None and value < float(min_v):
                violations.append(
                    f"Below minimum {min_v} {unit} in {spec['doc_id']} §{spec['section']}"
                )
            elif max_v is not None and value > float(max_v):
                violations.append(
                    f"Exceeds maximum {max_v} {unit} in {spec['doc_id']} §{spec['section']}"
                )

        return {
            "compliant": len(violations) == 0,
            "checked_value": f"{value} {unit}",
            "parameter": parameter,
            "violations": violations,
            "specs_checked": len(specs),
            "references": [f"{s['doc_id']} — {s['section']}" for s in specs],
        }

    return await asyncio.to_thread(_run)


async def find_related_specs(doc_id: str, direction: str = "both",
                              depth: int = 2) -> dict[str, Any]:
    from ..core.database import get_driver
    driver = get_driver()

    def _run():
        dir_clause = {
            "upstream": "<-[:REFERENCES*1..$depth]-",
            "downstream": "-[:REFERENCES*1..$depth]->",
            "both": "-[:REFERENCES*1..$depth]-",
        }[direction]
        with driver.session() as s:
            result = s.run(
                f"""
                MATCH (src:Document {{name: $doc_id}}){dir_clause}(rel:Document)
                WHERE rel <> src
                RETURN DISTINCT rel.name AS doc_id, rel.title AS title
                LIMIT 20
                """,
                doc_id=doc_id, depth=depth,
            )
            return {"doc_id": doc_id, "direction": direction,
                    "related": [dict(r) for r in result]}

    return await asyncio.to_thread(_run)


async def trace_change_history(doc_id: str,
                                section_number: str | None = None) -> dict[str, Any]:
    from ..core.database import get_driver
    driver = get_driver()

    def _run():
        with driver.session() as s:
            result = s.run(
                """
                MATCH (d:Document {name: $doc_id})-[:HAS_CHANGE_RECORD]->(cr:ChangeRecord)
                RETURN cr.record_id AS record_id, cr.reason AS reason,
                       cr.approver AS approver, cr.effective_date AS date
                ORDER BY cr.effective_date DESC
                LIMIT 20
                """,
                doc_id=doc_id,
            )
            return {"doc_id": doc_id, "changes": [dict(r) for r in result]}

    return await asyncio.to_thread(_run)


async def get_hazards(procedure_name: str | None = None,
                      doc_id: str | None = None) -> dict[str, Any]:
    from ..core.database import get_driver
    driver = get_driver()

    def _run():
        filters = []
        params: dict = {}
        if procedure_name:
            filters.append("(s.content CONTAINS $name OR s.title CONTAINS $name)")
            params["name"] = procedure_name
        if doc_id:
            filters.append("s.doc_id = $doc_id")
            params["doc_id"] = doc_id
        where = "WHERE " + " AND ".join(filters) if filters else ""
        with driver.session() as s:
            result = s.run(
                f"""
                MATCH (s:Section)-[:WARNS_OF]->(h:Hazard)
                {where}
                RETURN h.hazard_id AS id, h.description AS description,
                       h.severity AS severity, s.title AS section
                ORDER BY h.severity DESC
                LIMIT 20
                """,
                **params,
            )
            return {"hazards": [dict(r) for r in result]}

    return await asyncio.to_thread(_run)


async def get_inspection_requirements(procedure_name: str | None = None,
                                       doc_id: str | None = None) -> dict[str, Any]:
    from ..core.database import get_driver
    driver = get_driver()

    def _run():
        filters = []
        params: dict = {}
        if procedure_name:
            filters.append("(s.content CONTAINS $name OR s.title CONTAINS $name)")
            params["name"] = procedure_name
        if doc_id:
            filters.append("s.doc_id = $doc_id")
            params["doc_id"] = doc_id
        where = "WHERE " + " AND ".join(filters) if filters else ""
        with driver.session() as s:
            result = s.run(
                f"""
                MATCH (s:Section)-[:REQUIRES_INSPECTION]->(i:Inspection)
                {where}
                RETURN i.insp_id AS id, i.method AS method,
                       i.frequency AS frequency,
                       i.acceptance_criteria AS acceptance_criteria,
                       s.title AS section
                LIMIT 20
                """,
                **params,
            )
            return {"inspections": [dict(r) for r in result]}

    return await asyncio.to_thread(_run)


# ─── Skill dispatcher ─────────────────────────────────────────────────────────

SKILL_HANDLERS = {
    "query_procedure": query_procedure,
    "check_compliance": check_compliance,
    "find_related_specs": find_related_specs,
    "trace_change_history": trace_change_history,
    "get_hazards": get_hazards,
    "get_inspection_requirements": get_inspection_requirements,
}


async def dispatch_skill(name: str, args: dict) -> Any:
    handler = SKILL_HANDLERS.get(name)
    if not handler:
        raise ValueError(f"Unknown skill: {name}")
    return await handler(**args)
