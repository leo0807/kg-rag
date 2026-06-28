"""
Graph self-improvement: entity alignment, embedding persistence, auto-completion,
active-learning annotation queue.

POST /api/admin/graph/auto-complete  — 检测孤立节点并补全实体
POST /api/admin/graph/entity-align   — 跨文档实体对齐（同义异名消歧）
POST /api/admin/graph/embed-persist  — 将 GraphSAGE Embedding 写入 Milvus
GET  /api/admin/graph/active-learning — 低置信度边推送给专家确认
POST /api/admin/graph/active-learning/{edge_id}/confirm
POST /api/admin/graph/active-learning/{edge_id}/reject
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/graph", tags=["graph-learn"])

_CONFIDENCE_THRESHOLD = 0.9   # SIMILAR_TO edges below this go to active-learning queue


# ---------------------------------------------------------------------------
# Auto-complete isolated nodes
# ---------------------------------------------------------------------------

def _find_isolated_sections(limit: int = 50) -> list[str]:
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (sec:Section)
            WHERE NOT (sec)-[:REQUIRES_TOOL]->()
              AND NOT (sec)-[:USES_MATERIAL]->()
              AND NOT (sec)-[:INVOLVES_PROCESS]->()
            RETURN sec.chunk_id AS chunk_id LIMIT $lim
        """, lim=limit)
        return [r["chunk_id"] for r in result]


async def _auto_complete_task(limit: int) -> dict[str, Any]:
    isolated = await asyncio.to_thread(_find_isolated_sections, limit)
    if not isolated:
        return {"queued": 0, "chunk_ids": []}
    try:
        from ...tasks.entity_tasks import extract_entities_for_chunk  # noqa: PLC0415
        for cid in isolated:
            await asyncio.to_thread(extract_entities_for_chunk, cid)
    except ImportError:
        log.info("auto-complete: entity_tasks not available — dry run for %d chunks", len(isolated))
    return {"queued": len(isolated), "chunk_ids": isolated}


@router.post("/auto-complete")
async def auto_complete(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=500),
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Queue isolated sections for LLM entity re-extraction."""
    background_tasks.add_task(_auto_complete_task, limit)
    return {"ok": True, "status": "queued", "max_chunks": limit}


# ---------------------------------------------------------------------------
# Entity alignment
# ---------------------------------------------------------------------------

def _find_candidate_pairs() -> list[dict]:
    """Find node pairs with similar names that might be the same entity."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (a:Document), (b:Document)
            WHERE id(a) < id(b)
              AND a.doc_id IS NOT NULL AND b.doc_id IS NOT NULL
              AND apoc.text.levenshteinSimilarity(a.doc_id, b.doc_id) > 0.85
              AND a.doc_id <> b.doc_id
            RETURN a.doc_id AS a_id, b.doc_id AS b_id,
                   apoc.text.levenshteinSimilarity(a.doc_id, b.doc_id) AS similarity
            LIMIT 20
        """)
        return [dict(r) for r in result]


def _merge_nodes(a_id: str, b_id: str) -> None:
    """Merge node b into node a (APOC required)."""
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MATCH (a:Document {doc_id: $a}), (b:Document {doc_id: $b_id})
            CALL apoc.refactor.mergeNodes([a, b], {
              properties: 'combine',
              mergeRels: true
            }) YIELD node
            RETURN node
        """, a=a_id, b_id=b_id)


@router.post("/entity-align")
async def entity_align(
    background_tasks: BackgroundTasks,
    dry_run: bool = Query(True, description="Preview only — set false to merge"),
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """
    Detect and optionally merge cross-document entities with near-identical IDs.
    Uses APOC levenshtein similarity; requires APOC plugin.
    """
    try:
        pairs = await asyncio.to_thread(_find_candidate_pairs)
    except Exception as exc:
        log.warning("entity_align: APOC not available — %s", exc)
        return {"ok": False, "error": "APOC plugin required", "pairs": []}

    if not dry_run and pairs:
        for pair in pairs[:10]:
            background_tasks.add_task(_merge_nodes, pair["a_id"], pair["b_id"])

    return {
        "dry_run":    dry_run,
        "pair_count": len(pairs),
        "pairs":      pairs,
        "note":       "Set dry_run=false to merge pairs automatically.",
    }


# ---------------------------------------------------------------------------
# Embedding persistence to Milvus
# ---------------------------------------------------------------------------

def _load_and_persist_embeddings() -> dict[str, Any]:
    """Load pre-computed node embeddings from Neo4j and upsert into Milvus."""
    try:
        from pymilvus import (  # noqa: PLC0415
            connections, FieldSchema, CollectionSchema, DataType, Collection
        )
        import os  # noqa: PLC0415

        connections.connect(
            alias="default",
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=int(os.getenv("MILVUS_PORT", "19530")),
        )
        fields = [
            FieldSchema("chunk_id", DataType.VARCHAR, max_length=200, is_primary=True),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=768),
        ]
        schema = CollectionSchema(fields, "GraphSAGE node embeddings")
        col = Collection("graph_node_embeddings", schema, using="default")
        col.create_index("embedding", {"metric_type": "COSINE", "index_type": "IVF_FLAT",
                                        "params": {"nlist": 128}})
    except ImportError:
        log.info("embed_persist: pymilvus not available — skipping")
        return {"ok": False, "reason": "pymilvus not installed"}

    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            "MATCH (sec:Section) WHERE sec.graphsage_embedding IS NOT NULL "
            "RETURN sec.chunk_id AS chunk_id, sec.graphsage_embedding AS emb LIMIT 5000"
        )
        rows = [dict(r) for r in result]

    if not rows:
        return {"ok": True, "persisted": 0, "note": "No embeddings found in Neo4j"}

    try:
        col.upsert(
            data=[[r["chunk_id"] for r in rows], [r["emb"] for r in rows]],
            partition_name="_default",
        )
        col.flush()
        return {"ok": True, "persisted": len(rows)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/embed-persist")
async def embed_persist(
    background_tasks: BackgroundTasks,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Persist GraphSAGE node embeddings from Neo4j into Milvus (background)."""
    background_tasks.add_task(
        lambda: asyncio.run(_load_and_persist_embeddings() and None)
    )
    return {"ok": True, "status": "queued"}


# ---------------------------------------------------------------------------
# Active learning queue
# ---------------------------------------------------------------------------

@router.get("/active-learning")
async def active_learning_queue(
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """
    Return SIMILAR_TO edges with confidence below threshold for expert review.
    """
    def _query():
        driver = get_driver()
        with driver.session() as s:
            result = s.run("""
                MATCH (a)-[r:SIMILAR_TO]->(b)
                WHERE r.confidence IS NOT NULL
                  AND r.confidence < $threshold
                  AND coalesce(r.reviewed, false) = false
                RETURN elementId(r) AS edge_id,
                       a.chunk_id AS source_id, a.title AS source_title,
                       b.chunk_id AS target_id, b.title AS target_title,
                       r.confidence AS confidence
                ORDER BY r.confidence ASC
                LIMIT $lim
            """, threshold=_CONFIDENCE_THRESHOLD, lim=limit)
            return [dict(r) for r in result]

    edges = await asyncio.to_thread(_query)
    return {
        "threshold": _CONFIDENCE_THRESHOLD,
        "count":     len(edges),
        "edges":     edges,
    }


@router.post("/active-learning/{edge_id}/confirm")
async def confirm_edge(
    edge_id: str,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MATCH ()-[r]->() WHERE elementId(r) = $eid "
            "SET r.reviewed = true, r.confirmed = true",
            eid=edge_id,
        )
    return {"ok": True, "edge_id": edge_id, "action": "confirmed"}


@router.post("/active-learning/{edge_id}/reject")
async def reject_edge(
    edge_id: str,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MATCH ()-[r]->() WHERE elementId(r) = $eid "
            "SET r.reviewed = true, r.confirmed = false",
            eid=edge_id,
        )
    return {"ok": True, "edge_id": edge_id, "action": "rejected"}
