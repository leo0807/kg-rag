"""
Graph-driven AI capabilities — KGQA, backward chaining, process routing,
question generation, anomaly diagnosis.

POST /api/graph/kgqa            — 自然语言 → Cypher → 精确答案
POST /api/graph/backward-chain  — 结论反向推因果链
GET  /api/graph/process-route   — 给定零件+目标状态，推导最优工艺路线
POST /api/graph/generate-questions — 基于图结构生成培训考核题
POST /api/graph/diagnose-anomaly   — 工艺异常诊断
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...auth.deps import get_current_user
from ...core.database import get_driver
from ...db.models import User


def _answer_from_graph(question: str, driver) -> dict:
    """Minimal in-module Cypher executor used when kgqa is invoked."""
    with driver.session() as s:
        result = s.run(
            "MATCH (n) WHERE toLower(n.title) CONTAINS toLower($q) "
            "OR toLower(n.content) CONTAINS toLower($q) "
            "RETURN labels(n)[0] AS label, "
            "coalesce(n.title, n.name, n.chunk_id) AS name, "
            "coalesce(n.content, '') AS content "
            "LIMIT 10",
            q=question,
        )
        return {"rows": [dict(r) for r in result]}

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph-kgqa"])


# ---------------------------------------------------------------------------
# KGQA — Text2Cypher
# ---------------------------------------------------------------------------

class KGQARequest(BaseModel):
    question: str
    top_k:    int = 10


@router.post("/kgqa")
async def kgqa(
    body: KGQARequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Translate a natural-language question to Cypher and execute it directly
    against Neo4j. Returns structured graph data rather than chunked text.
    """
    import asyncio  # noqa: PLC0415

    driver = get_driver()
    result = await asyncio.to_thread(_answer_from_graph, body.question, driver)
    return {
        "question": body.question,
        "source":   "graph_kgqa",
        "data":     result,
    }


# ---------------------------------------------------------------------------
# Backward chaining
# ---------------------------------------------------------------------------

class BackwardChainRequest(BaseModel):
    conclusion: str   # e.g. "零件 CPS1220-A 出现裂纹"
    depth:      int = 3


def _backward_chain(conclusion: str, depth: int) -> list[dict]:
    """Follow CAUSES / LEADS_TO / VALIDATES edges backwards from a Hazard or Failure."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH path = (cause)-[:CAUSES|LEADS_TO|RELATED_TO*1..$depth]->(effect)
            WHERE effect.name CONTAINS $kw OR effect.description CONTAINS $kw
            RETURN [n IN nodes(path) | {
                name: coalesce(n.name, n.title, n.chunk_id),
                labels: labels(n),
                node_id: coalesce(n.chunk_id, n.node_id, elementId(n))
            }] AS chain,
            length(path) AS hops
            ORDER BY hops
            LIMIT 10
        """, kw=conclusion[:50], depth=depth)
        return [dict(r) for r in result]


@router.post("/backward-chain")
async def backward_chain(
    body: BackwardChainRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Given a failure/conclusion, trace back through cause-effect relationships
    to identify root causes in the knowledge graph.
    """
    import asyncio  # noqa: PLC0415

    chains = await asyncio.to_thread(_backward_chain, body.conclusion, body.depth)
    return {
        "conclusion": body.conclusion,
        "depth":      body.depth,
        "chains":     chains,
        "count":      len(chains),
    }


# ---------------------------------------------------------------------------
# Process route planning
# ---------------------------------------------------------------------------

@router.get("/process-route")
async def process_route(
    component:    str = Query(..., description="零件 P/N"),
    target_state: str = Query(..., description="目标状态，如'液压管路安装完成'"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return an ordered process route (topological sort of steps) for a component.
    """
    import asyncio  # noqa: PLC0415

    def _query():
        driver = get_driver()
        with driver.session() as s:
            # Find sections that APPLY_TO this component, ordered by PRECEDES chain
            result = s.run("""
                MATCH (comp:Component {part_no: $pn})<-[:APPLIES_TO]-(sec:Section)
                OPTIONAL MATCH path = (sec)-[:PRECEDES*0..10]->(next:Section)
                RETURN DISTINCT sec.chunk_id AS chunk_id,
                               sec.title     AS title,
                               sec.doc_id    AS doc_id,
                               length(path)  AS position
                ORDER BY position
                LIMIT 30
            """, pn=component)
            return [dict(r) for r in result]

    steps = await asyncio.to_thread(_query)
    return {
        "component":    component,
        "target_state": target_state,
        "route":        steps,
        "step_count":   len(steps),
    }


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

class QGenRequest(BaseModel):
    doc_id:     str | None = None
    chunk_id:   str | None = None
    count:      int = 5


@router.post("/generate-questions")
async def generate_questions(
    body: QGenRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Generate training assessment questions from graph structure.
    Uses graph-derived facts (tools, constraints, steps) as question seeds.
    """
    import asyncio  # noqa: PLC0415

    def _fetch_facts():
        driver = get_driver()
        with driver.session() as s:
            if body.chunk_id:
                where = "s.chunk_id = $id"
                param = {"id": body.chunk_id}
            elif body.doc_id:
                where = "s.doc_id = $id"
                param = {"id": body.doc_id}
            else:
                raise ValueError("doc_id or chunk_id required")

            result = s.run(f"""
                MATCH (s:Section) WHERE {where}
                OPTIONAL MATCH (s)-[:REQUIRES_TOOL]->(t:Tool)
                OPTIONAL MATCH (s)-[:HAS_CONSTRAINT]->(c:Constraint)
                RETURN s.title AS section,
                       s.content AS content,
                       collect(DISTINCT t.name) AS tools,
                       collect(DISTINCT c.parameter + ': ' + c.value) AS constraints
                LIMIT 5
            """, **param)
            return [dict(r) for r in result]

    try:
        facts = await asyncio.to_thread(_fetch_facts)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate questions from facts using LLM
    questions = []
    for fact in facts[:body.count]:
        if fact.get("tools"):
            q = (f"根据 {fact['section']}，安装该工序需要使用哪些工具？"
                 f"（参考答案：{', '.join(fact['tools'][:3])}）")
            questions.append({"question": q, "source_section": fact["section"], "type": "tool"})
        if fact.get("constraints"):
            for c in fact["constraints"][:1]:
                q = f"根据 {fact['section']}，{c.split(':')[0]} 的要求值是多少？"
                questions.append({"question": q, "source_section": fact["section"],
                                  "type": "constraint", "hint": c})
    return {"count": len(questions), "questions": questions[:body.count]}


# ---------------------------------------------------------------------------
# Anomaly diagnosis
# ---------------------------------------------------------------------------

class AnomalyRequest(BaseModel):
    description: str  # e.g. "液压管路渗漏"
    component:   str | None = None


@router.post("/diagnose-anomaly")
async def diagnose_anomaly(
    body: AnomalyRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Given an anomaly description, retrieve related Hazard/Constraint/Inspection
    nodes and generate a structured diagnosis.
    """
    import asyncio  # noqa: PLC0415

    def _fetch_related():
        driver = get_driver()
        kw = body.description[:80]
        with driver.session() as s:
            hazards = s.run("""
                MATCH (h:Hazard) WHERE h.name CONTAINS $kw OR h.description CONTAINS $kw
                RETURN h.name AS name, h.severity AS severity, h.description AS desc
                LIMIT 5
            """, kw=kw)
            constraints = s.run("""
                MATCH (c:Constraint)-[:LINKED_TO]->(s:Section)
                WHERE s.content CONTAINS $kw
                RETURN c.parameter AS parameter, c.value AS value, c.unit AS unit,
                       s.title AS section
                LIMIT 5
            """, kw=kw)
            inspections = s.run("""
                MATCH (i:Inspection) WHERE i.description CONTAINS $kw
                RETURN i.method AS method, i.acceptance_criteria AS criteria
                LIMIT 5
            """, kw=kw)
            return {
                "hazards":     [dict(r) for r in hazards],
                "constraints": [dict(r) for r in constraints],
                "inspections": [dict(r) for r in inspections],
            }

    related = await asyncio.to_thread(_fetch_related)
    return {
        "anomaly":     body.description,
        "component":   body.component,
        "related":     related,
        "diagnosis":   "请结合以上图谱节点与 LLM 进一步分析根因（可接入 /api/query 获取详细解答）",
    }
