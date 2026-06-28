"""
Graph algorithm services via Neo4j GDS (Graph Data Science library).
Requires the GDS plugin to be installed in Neo4j.
"""
from __future__ import annotations

import logging
from typing import Any

from ...core.database import get_driver

log = logging.getLogger(__name__)

_GRAPH_NAME = "sectionGraph"


def _ensure_projection(session) -> None:
    """Project Section nodes for GDS (idempotent)."""
    existing = session.run(
        "CALL gds.graph.exists($name) YIELD exists",
        name=_GRAPH_NAME,
    ).single()
    if existing and existing["exists"]:
        return
    session.run(
        """
        CALL gds.graph.project(
            $name,
            'Section',
            {
                NEXT_SECTION: {orientation: 'UNDIRECTED'},
                HAS_SUBSECTION: {orientation: 'UNDIRECTED'},
                SIMILAR_TO: {orientation: 'UNDIRECTED'},
                REFERENCES: {orientation: 'UNDIRECTED'}
            }
        )
        """,
        name=_GRAPH_NAME,
    )


def _drop_projection(session) -> None:
    try:
        session.run("CALL gds.graph.drop($name)", name=_GRAPH_NAME)
    except Exception:
        pass


# ─── PageRank ────────────────────────────────────────────────────────────────

def run_pagerank(write: bool = True, top_k: int = 20) -> list[dict]:
    """
    Compute PageRank on Section nodes.
    Writes `pagerank` property if write=True.
    Returns top_k nodes by score.
    """
    driver = get_driver()
    with driver.session() as s:
        _ensure_projection(s)
        if write:
            s.run(
                """
                CALL gds.pageRank.write($graph, {
                    writeProperty: 'pagerank',
                    maxIterations: 20,
                    dampingFactor: 0.85
                })
                """,
                graph=_GRAPH_NAME,
            )
        result = s.run(
            """
            MATCH (n:Section)
            WHERE n.pagerank IS NOT NULL
            RETURN n.chunk_id AS chunk_id, n.title AS title,
                   n.doc_id AS doc_id, n.pagerank AS score
            ORDER BY n.pagerank DESC
            LIMIT $k
            """,
            k=top_k,
        )
        return [dict(r) for r in result]


# ─── Louvain Community Detection ─────────────────────────────────────────────

def run_louvain(write: bool = True) -> dict[str, Any]:
    """
    Run Louvain community detection.
    Writes `community_id` property if write=True.
    Returns community count and sample stats.
    """
    driver = get_driver()
    with driver.session() as s:
        _ensure_projection(s)
        if write:
            stats = s.run(
                """
                CALL gds.louvain.write($graph, {
                    writeProperty: 'community_id',
                    maxLevels: 10,
                    maxIterations: 10,
                    tolerance: 0.0001
                })
                YIELD communityCount, modularity, levels
                RETURN communityCount, modularity, levels
                """,
                graph=_GRAPH_NAME,
            ).single()
            return dict(stats) if stats else {}
        else:
            result = s.run(
                """
                CALL gds.louvain.stream($graph)
                YIELD nodeId, communityId
                RETURN gds.util.asNode(nodeId).chunk_id AS chunk_id, communityId
                LIMIT 100
                """
            )
            return {"communities": [dict(r) for r in result]}


def get_communities(top_k: int = 10) -> list[dict]:
    """Return top communities by size with representative sections."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (n:Section)
            WHERE n.community_id IS NOT NULL
            WITH n.community_id AS cid, collect(n) AS members
            ORDER BY size(members) DESC
            LIMIT $k
            RETURN cid,
                   size(members) AS member_count,
                   [m IN members[..3] | m.title][0..3] AS sample_titles
            """,
            k=top_k,
        )
        return [dict(r) for r in result]


# ─── Betweenness Centrality ───────────────────────────────────────────────────

def run_betweenness(write: bool = True, top_k: int = 20) -> list[dict]:
    """
    Compute Betweenness Centrality — finds "bridge" nodes between clusters.
    """
    driver = get_driver()
    with driver.session() as s:
        _ensure_projection(s)
        if write:
            s.run(
                """
                CALL gds.betweenness.write($graph, {
                    writeProperty: 'betweenness'
                })
                """,
                graph=_GRAPH_NAME,
            )
        result = s.run(
            """
            MATCH (n:Section)
            WHERE n.betweenness IS NOT NULL
            RETURN n.chunk_id AS chunk_id, n.title AS title,
                   n.doc_id AS doc_id, n.betweenness AS score
            ORDER BY n.betweenness DESC
            LIMIT $k
            """,
            k=top_k,
        )
        return [dict(r) for r in result]


# ─── Shortest Path ────────────────────────────────────────────────────────────

def shortest_path(from_chunk_id: str, to_chunk_id: str) -> list[dict]:
    """
    Return the shortest knowledge path between two Section/Document nodes.
    Uses bidirectional BFS via native Cypher (no GDS required).
    """
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (start {chunk_id: $from}), (end {chunk_id: $to})
            MATCH path = shortestPath((start)-[*..8]-(end))
            RETURN [n IN nodes(path) | {
                id: coalesce(n.chunk_id, n.name, n.part_no, ''),
                label: labels(n)[0],
                title: coalesce(n.title, n.name, '')
            }] AS nodes,
            [r IN relationships(path) | type(r)] AS relations,
            length(path) AS hops
            LIMIT 3
            """,
            **{"from": from_chunk_id, "to": to_chunk_id},
        )
        return [dict(r) for r in result]


# ─── Node Similarity (auto SIMILAR_TO edges) ─────────────────────────────────

def run_node_similarity(threshold: float = 0.5, write: bool = True,
                        top_k: int = 10) -> dict:
    """
    Compute node similarity based on shared neighbors.
    Creates SIMILAR_TO edges between similar Section nodes.
    """
    driver = get_driver()
    with driver.session() as s:
        _ensure_projection(s)
        if write:
            stats = s.run(
                """
                CALL gds.nodeSimilarity.write($graph, {
                    writeRelationshipType: 'SIMILAR_TO',
                    writeProperty: 'score',
                    similarityCutoff: $threshold,
                    topK: $topK
                })
                YIELD nodesCompared, relationshipsWritten
                RETURN nodesCompared, relationshipsWritten
                """,
                graph=_GRAPH_NAME,
                threshold=threshold,
                topK=top_k,
            ).single()
            return dict(stats) if stats else {}
        return {}


# ─── Knowledge Coverage Heatmap ──────────────────────────────────────────────

def coverage_heatmap() -> list[dict]:
    """
    Return coverage stats per document:
    what fraction of sections have Tool/Material/Process/Constraint links.
    """
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (d:Document)-[:HAS_SECTION]->(sec:Section)
            WITH d.name AS doc_id,
                 count(sec) AS total_sections,
                 count(CASE WHEN (sec)-[:REQUIRES_TOOL]->() THEN 1 END) AS has_tool,
                 count(CASE WHEN (sec)-[:USES_MATERIAL]->() THEN 1 END) AS has_mat,
                 count(CASE WHEN (sec)-[:HAS_CONSTRAINT]->() THEN 1 END) AS has_con,
                 count(CASE WHEN (sec)-[:WARNS_OF]->() THEN 1 END) AS has_hazard
            RETURN doc_id, total_sections,
                   round(100.0 * has_tool / total_sections, 1) AS tool_pct,
                   round(100.0 * has_mat / total_sections, 1) AS mat_pct,
                   round(100.0 * has_con / total_sections, 1) AS constraint_pct,
                   round(100.0 * has_hazard / total_sections, 1) AS hazard_pct
            ORDER BY constraint_pct ASC
            """
        )
        return [dict(r) for r in result]
