"""
Advanced retrieval strategies beyond basic vector/graph search.

POST /api/query/ppr           — 个性化 PageRank 检索
POST /api/query/path-aware    — 关系路径感知检索
POST /api/query/temporal      — 时序感知检索（优先最新版本）
POST /api/query/constraint    — 约束感知检索（数值范围匹配）
POST /api/query/subgraph      — 动态子图提取（2跳上下文）
POST /api/query/reasoning-chain — 推理链图谱化记录
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...auth.deps import get_current_user
from ...core.database import get_driver
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/query", tags=["adv-retrieval"])

_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([A-Za-z°%]+)?")


# ---------------------------------------------------------------------------
# Personalised PageRank
# ---------------------------------------------------------------------------

class PPRRequest(BaseModel):
    question:    str
    seed_ids:    list[str] = []   # chunk_ids to use as seed nodes
    top_k:       int = 10
    damping:     float = 0.85


def _ppr_query(seed_ids: list[str], top_k: int, damping: float) -> list[dict]:
    if not seed_ids:
        return []
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (seed:Section)
            WHERE seed.chunk_id IN $seeds
            CALL gds.personalizedPageRank.stream('section-graph', {
                sourceNodes: collect(seed),
                dampingFactor: $damp
            })
            YIELD nodeId, score
            MATCH (n:Section) WHERE id(n) = nodeId
            RETURN n.chunk_id AS chunk_id, n.title AS title,
                   n.doc_id AS doc_id, score
            ORDER BY score DESC
            LIMIT $k
        """, seeds=seed_ids, damp=damping, k=top_k)
        return [dict(r) for r in result]


@router.post("/ppr")
async def ppr_retrieval(
    body: PPRRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Personalised PageRank retrieval seeded from anchor nodes.
    Falls back to direct Neo4j traversal if GDS is unavailable.
    """
    try:
        results = await asyncio.to_thread(_ppr_query, body.seed_ids, body.top_k, body.damping)
    except Exception as exc:
        log.warning("PPR via GDS failed (%s) — falling back to BFS", exc)
        driver = get_driver()
        with driver.session() as s:
            r = s.run("""
                MATCH (seed:Section)-[:REFERENCES|SIMILAR_TO|PRECEDES*1..2]-(n:Section)
                WHERE seed.chunk_id IN $seeds
                  AND NOT n.chunk_id IN $seeds
                RETURN DISTINCT n.chunk_id AS chunk_id, n.title AS title,
                       n.doc_id AS doc_id, 0.5 AS score
                LIMIT $k
            """, seeds=body.seed_ids, k=body.top_k)
            results = [dict(row) for row in r]
    return {"question": body.question, "strategy": "ppr", "results": results}


# ---------------------------------------------------------------------------
# Path-aware retrieval
# ---------------------------------------------------------------------------

class PathAwareRequest(BaseModel):
    question: str
    chunk_ids: list[str]  # candidate nodes from prior vector retrieval
    top_k:     int = 10


@router.post("/path-aware")
async def path_aware_retrieval(
    body: PathAwareRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Re-rank candidates by relationship path type:
    direct (shared Tool) > indirect (shared Material > Process).
    """
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            UNWIND $ids AS cid
            MATCH (a:Section {chunk_id: cid}), (b:Section)
            WHERE b.chunk_id IN $ids AND id(a) < id(b)
            OPTIONAL MATCH direct  = (a)-[:REQUIRES_TOOL|USES_MATERIAL]->(x)<-[:REQUIRES_TOOL|USES_MATERIAL]-(b)
            OPTIONAL MATCH indirect = (a)-[:INVOLVES_PROCESS]->(p)<-[:INVOLVES_PROCESS]-(b)
            RETURN a.chunk_id AS a_id, b.chunk_id AS b_id,
                   CASE WHEN direct IS NOT NULL THEN 'direct' ELSE 'indirect' END AS path_type,
                   CASE WHEN direct IS NOT NULL THEN 1.0 ELSE 0.5 END AS weight
            ORDER BY weight DESC
            LIMIT $k
        """, ids=body.chunk_ids, k=body.top_k)
        pairs = [dict(r) for r in result]
    return {"strategy": "path_aware", "ranked_pairs": pairs}


# ---------------------------------------------------------------------------
# Temporal retrieval
# ---------------------------------------------------------------------------

class TemporalRequest(BaseModel):
    question: str
    doc_id:   str | None = None
    top_k:    int = 10


@router.post("/temporal")
async def temporal_retrieval(
    body: TemporalRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return sections preferring latest document versions; penalise superseded sections."""
    driver = get_driver()
    with driver.session() as s:
        extra = "AND sec.doc_id = $did " if body.doc_id else ""
        result = s.run(
            f"""
            MATCH (sec:Section)-[:BELONGS_TO]->(doc:Document)
            WHERE NOT (doc)-[:OBSOLETED_BY]->()
              {extra}
            OPTIONAL MATCH (doc)-[:SUPERSEDED_BY]->(newer:Document)
            RETURN sec.chunk_id AS chunk_id, sec.title AS title,
                   doc.doc_id AS doc_id, doc.version AS version,
                   newer IS NULL AS is_latest,
                   CASE WHEN newer IS NULL THEN 1.0 ELSE 0.3 END AS recency_weight
            ORDER BY recency_weight DESC, doc.version DESC
            LIMIT $k
            """,
            k=body.top_k, **{"did": body.doc_id} if body.doc_id else {},
        )
        rows = [dict(r) for r in result]
    return {"strategy": "temporal", "results": rows}


# ---------------------------------------------------------------------------
# Constraint-aware retrieval
# ---------------------------------------------------------------------------

class ConstraintRequest(BaseModel):
    question: str
    top_k:    int = 10


@router.post("/constraint")
async def constraint_aware_retrieval(
    body: ConstraintRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Detect numeric values in question and prioritise sections whose
    Constraint.value range covers that number.
    """
    nums = _NUM_RE.findall(body.question)
    if not nums:
        return {"strategy": "constraint", "note": "No numeric values detected", "results": []}
    value, unit = nums[0]
    value_f = float(value)
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (c:Constraint)<-[:HAS_CONSTRAINT]-(sec:Section)
            WHERE c.value IS NOT NULL
              AND (toFloat(c.value) <= $val OR c.value CONTAINS $val_str)
            RETURN DISTINCT sec.chunk_id AS chunk_id, sec.title AS title,
                   sec.doc_id AS doc_id, c.parameter AS parameter,
                   c.value AS value, c.unit AS unit
            ORDER BY abs(toFloat(c.value) - $val)
            LIMIT $k
        """, val=value_f, val_str=value, k=body.top_k)
        rows = [dict(r) for r in result]
    return {"strategy": "constraint", "detected_value": value, "unit": unit, "results": rows}


# ---------------------------------------------------------------------------
# Dynamic subgraph extraction
# ---------------------------------------------------------------------------

class SubgraphRequest(BaseModel):
    chunk_ids: list[str]
    hops:      int = 2


@router.post("/subgraph")
async def dynamic_subgraph(
    body: SubgraphRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Extract 2-hop subgraph around answer sections for LLM context enrichment."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(f"""
            MATCH (seed:Section) WHERE seed.chunk_id IN $ids
            CALL {{
                WITH seed
                MATCH (seed)-[r*1..{body.hops}]-(neighbor)
                RETURN neighbor, r
            }}
            RETURN DISTINCT labels(neighbor)[0] AS label,
                   coalesce(neighbor.name, neighbor.chunk_id, neighbor.tool_id) AS name,
                   type(r[-1]) AS rel_type
            LIMIT 200
        """, ids=body.chunk_ids)
        nodes = [dict(r) for r in result]
    return {"chunk_ids": body.chunk_ids, "hops": body.hops,
            "subgraph_nodes": len(nodes), "nodes": nodes}


# ---------------------------------------------------------------------------
# Reasoning chain persistence
# ---------------------------------------------------------------------------

class ReasoningChainBody(BaseModel):
    query_id:    str
    question:    str
    steps: list[dict]  # [{sub_question, node_ids, rel_types, sub_answer}]
    final_answer: str


@router.post("/reasoning-chain")
async def persist_reasoning_chain(
    body: ReasoningChainBody,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Write multi-hop reasoning steps to Neo4j as a QueryChain graph."""
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MERGE (q:QueryChain {query_id: $qid})
            SET q.question = $question, q.final_answer = $ans,
                q.user_id = $uid, q.created_at = $ts
        """, qid=body.query_id, question=body.question,
            ans=body.final_answer, uid=str(user.id),
            ts=datetime.now(timezone.utc).isoformat())
        for i, step in enumerate(body.steps):
            s.run("""
                MATCH (q:QueryChain {query_id: $qid})
                MERGE (qs:QueryStep {query_id: $qid, step_order: $i})
                SET qs.sub_question = $sq, qs.sub_answer = $sa
                MERGE (q)-[:HAS_STEP {order: $i}]->(qs)
                WITH qs
                UNWIND $node_ids AS nid
                  MATCH (sec:Section {chunk_id: nid})
                  MERGE (qs)-[:DERIVED_FROM_NODE]->(sec)
            """, qid=body.query_id, i=i,
                sq=step.get("sub_question", ""), sa=step.get("sub_answer", ""),
                node_ids=step.get("node_ids", []))
    return {"ok": True, "query_id": body.query_id, "steps_written": len(body.steps)}
