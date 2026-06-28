"""
Graph analytics and health endpoints.
Wraps graph_algorithms.py + conflict_detection.py services.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query

from ...services.graph.graph_algorithms import (
    coverage_heatmap,
    get_communities,
    run_betweenness,
    run_louvain,
    run_pagerank,
    shortest_path,
)
from ...services.graph.conflict_detection import (
    check_version_consistency,
    detect_constraint_conflicts,
    detect_cycles_in_precedes,
    graph_health_summary,
    scan_dangling_references,
    validate_process_integrity,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph-analytics"])


@router.get("/health")
async def get_graph_health():
    """Six-metric health dashboard snapshot."""
    return await asyncio.to_thread(graph_health_summary)


@router.get("/pagerank")
async def get_pagerank(top_k: int = Query(20, ge=1, le=200),
                       write: bool = Query(False)):
    """Return top sections by PageRank (requires Neo4j GDS)."""
    return await asyncio.to_thread(run_pagerank, write, top_k)


@router.post("/pagerank/compute")
async def compute_pagerank():
    """Recompute and write PageRank scores to Section nodes."""
    result = await asyncio.to_thread(run_pagerank, True, 20)
    return {"status": "computed", "top_nodes": result[:5]}


@router.get("/communities")
async def get_graph_communities(top_k: int = Query(10, ge=1, le=50)):
    """Return Louvain communities by size."""
    return await asyncio.to_thread(get_communities, top_k)


@router.post("/communities/compute")
async def compute_communities():
    """Run Louvain community detection and write community_id to nodes."""
    result = await asyncio.to_thread(run_louvain, True)
    return {"status": "computed", **result}


@router.get("/betweenness")
async def get_betweenness(top_k: int = Query(20, ge=1, le=100)):
    """Return top 'bridge' sections by Betweenness Centrality."""
    return await asyncio.to_thread(run_betweenness, False, top_k)


@router.post("/betweenness/compute")
async def compute_betweenness():
    """Recompute Betweenness Centrality (requires Neo4j GDS)."""
    result = await asyncio.to_thread(run_betweenness, True, 20)
    return {"status": "computed", "top_nodes": result[:5]}


@router.get("/path")
async def get_shortest_path(
    from_id: str = Query(..., description="Source chunk_id"),
    to_id: str = Query(..., description="Target chunk_id"),
):
    """Return shortest knowledge path between two nodes."""
    return await asyncio.to_thread(shortest_path, from_id, to_id)


@router.get("/coverage-heatmap")
async def get_coverage_heatmap():
    """Return per-document entity coverage percentages."""
    return await asyncio.to_thread(coverage_heatmap)


@router.get("/conflicts")
async def get_conflicts(component: Optional[str] = Query(None)):
    """Detect constraint conflicts (same component, different values)."""
    return await asyncio.to_thread(detect_constraint_conflicts, component)


@router.post("/scan-dangling")
async def scan_dangling():
    """Scan for dangling REFERENCES edges."""
    return await asyncio.to_thread(scan_dangling_references)


@router.get("/integrity")
async def check_integrity():
    """Validate graph process integrity."""
    return await asyncio.to_thread(validate_process_integrity)


@router.get("/cycles")
async def check_cycles():
    """Detect cycles in PRECEDES/FOLLOWS step chains."""
    return await asyncio.to_thread(detect_cycles_in_precedes)


@router.get("/version-drift/{doc_id}")
async def version_drift(doc_id: str):
    """Check constraint value drift between document versions."""
    return await asyncio.to_thread(check_version_consistency, doc_id)
