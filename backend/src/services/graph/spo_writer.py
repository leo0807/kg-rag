"""Write SPO triples to Neo4j as an independent named knowledge graph."""
from __future__ import annotations

import hashlib
import logging
import time

from neo4j import Driver

logger = logging.getLogger(__name__)

_MERGE_NODE = """
MERGE (n:SPONode {node_id: $node_id})
SET n.name = $name, n.type = $type, n.graph_id = $graph_id
"""
_MERGE_REL = """
MATCH (s:SPONode {node_id: $s_id})
MATCH (o:SPONode {node_id: $o_id})
MERGE (s)-[r:SPO_REL {predicate: $predicate, graph_id: $graph_id}]->(o)
SET r.predicate_type = $p_type
"""
_LINK_ROOT = """
MATCH (kg:KnowledgeGraph {graph_id: $graph_id})
MATCH (n:SPONode {node_id: $node_id})
MERGE (kg)-[:CONTAINS_NODE]->(n)
"""


def _node_id(graph_id: str, name: str, node_type: str) -> str:
    key = f"{graph_id}|{name}|{node_type}"
    return "spo_" + hashlib.md5(key.encode()).hexdigest()[:12]


def create_spo_graph(
    driver: Driver,
    graph_id: str,
    doc_id: str,
    chapter: str,
    spo_results: list[dict],
) -> dict:
    """
    Write a named SPO knowledge graph into Neo4j.

    Isolation strategy (Community Edition compatible):
    - KnowledgeGraph root node tags the whole subgraph
    - SPONode nodes carry graph_id property
    - SPO_REL relationships carry graph_id property
    - CONTAINS_NODE edges link root → all nodes

    Returns summary dict.
    """
    node_count = 0
    edge_count = 0
    created_at = int(time.time())

    with driver.session() as session:
        # 1. Create or replace the KnowledgeGraph root node
        session.run(
            """
            MERGE (kg:KnowledgeGraph {graph_id: $graph_id})
            SET kg.doc_id     = $doc_id,
                kg.chapter    = $chapter,
                kg.created_at = $created_at,
                kg.status     = 'building'
            """,
            graph_id=graph_id, doc_id=doc_id,
            chapter=chapter, created_at=created_at,
        )

        # 2. Remove ALL previously generated SPO nodes for this graph (rebuild).
        # Must match by graph_id property, NOT via CONTAINS_NODE, because object nodes
        # were never linked via CONTAINS_NODE and would otherwise survive as orphans.
        session.run(
            "MATCH (n:SPONode {graph_id: $graph_id}) DETACH DELETE n",
            graph_id=graph_id,
        )

        # 3. Write SPO triples per section
        for item in spo_results:
            chunk_id = item["chunk_id"]
            triples: list[dict] = item.get("triples", [])
            if not triples:
                continue

            for t in triples:
                s_id = _node_id(graph_id, t["s"], t["s_type"])
                o_id = _node_id(graph_id, t["o"], t["o_type"])

                # Upsert subject node
                session.run(
                    """
                    MERGE (n:SPONode {node_id: $node_id})
                    SET n.name     = $name,
                        n.type     = $type,
                        n.graph_id = $graph_id
                    """,
                    node_id=s_id, name=t["s"], type=t["s_type"], graph_id=graph_id,
                )
                # Upsert object node
                session.run(
                    """
                    MERGE (n:SPONode {node_id: $node_id})
                    SET n.name     = $name,
                        n.type     = $type,
                        n.graph_id = $graph_id
                    """,
                    node_id=o_id, name=t["o"], type=t["o_type"], graph_id=graph_id,
                )
                # Create SPO_REL relationship
                session.run(
                    f"""
                    MATCH (s:SPONode {{node_id: $s_id}})
                    MATCH (o:SPONode {{node_id: $o_id}})
                    MERGE (s)-[r:SPO_REL {{predicate: $predicate, graph_id: $graph_id}}]->(o)
                    SET r.predicate_type = $p_type
                    """,
                    s_id=s_id, o_id=o_id,
                    predicate=t["p"], p_type=t["p_type"], graph_id=graph_id,
                )
                edge_count += 1

                # Link root → subject node
                session.run(
                    """
                    MATCH (kg:KnowledgeGraph {graph_id: $graph_id})
                    MATCH (n:SPONode {node_id: $node_id})
                    MERGE (kg)-[:CONTAINS_NODE]->(n)
                    """,
                    graph_id=graph_id, node_id=s_id,
                )
                # Link section → subject node as source
                session.run(
                    """
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    MATCH (n:SPONode {node_id: $node_id})
                    MERGE (sec)-[:SPO_SOURCE {graph_id: $graph_id}]->(n)
                    """,
                    chunk_id=chunk_id, node_id=s_id, graph_id=graph_id,
                )

        # 4. Count distinct SPONodes in this graph
        result = session.run(
            "MATCH (n:SPONode {graph_id: $graph_id}) RETURN count(n) AS cnt",
            graph_id=graph_id,
        )
        node_count = result.single()["cnt"]

        # 5. Update KnowledgeGraph metadata
        session.run(
            """
            MATCH (kg:KnowledgeGraph {graph_id: $graph_id})
            SET kg.status     = 'ready',
                kg.node_count = $node_count,
                kg.edge_count = $edge_count
            """,
            graph_id=graph_id, node_count=node_count, edge_count=edge_count,
        )

    logger.info("SPO 图谱写入完成: graph_id=%s, nodes=%d, edges=%d", graph_id, node_count, edge_count)
    return {"graph_id": graph_id, "node_count": node_count, "edge_count": edge_count}


def get_spo_graph_data(driver: Driver, graph_id: str, limit: int = 0) -> dict:
    """Return SPO subgraph for visualization.

    Uses BFS from the highest-degree seed to return a well-connected subgraph
    of at most `limit` nodes. Passing limit=0 returns all nodes (may be large).
    """
    with driver.session() as session:
        kg_result = session.run(
            "MATCH (kg:KnowledgeGraph {graph_id: $graph_id}) RETURN kg",
            graph_id=graph_id,
        ).single()
        if not kg_result:
            return {"nodes": [], "edges": [], "graph": None}

        kg = dict(kg_result["kg"])

        # Fetch all edges first (7k edges ≈ 1 MB, acceptable)
        edges_result = session.run(
            """
            MATCH (s:SPONode {graph_id: $graph_id})-[r:SPO_REL {graph_id: $graph_id}]->(o:SPONode)
            RETURN s.node_id AS source, o.node_id AS target,
                   r.predicate AS predicate, r.predicate_type AS predicate_type
            """,
            graph_id=graph_id,
        )
        all_edges = [dict(r) for r in edges_result]

        if not all_edges:
            return {"nodes": [], "edges": [], "graph": kg}

        # Build adjacency (undirected) for BFS
        adj: dict[str, list[str]] = {}
        degree: dict[str, int] = {}
        for e in all_edges:
            adj.setdefault(e["source"], []).append(e["target"])
            adj.setdefault(e["target"], []).append(e["source"])
            degree[e["source"]] = degree.get(e["source"], 0) + 1
            degree[e["target"]] = degree.get(e["target"], 0) + 1

        if limit > 0 and len(degree) > limit:
            # BFS from highest-degree seed, preferring high-degree neighbors
            seed = max(degree, key=lambda n: degree[n])
            visited: set[str] = {seed}
            queue = [seed]
            head = 0
            while head < len(queue) and len(visited) < limit:
                curr = queue[head]; head += 1
                neighbors = sorted(
                    adj.get(curr, []),
                    key=lambda n: degree.get(n, 0),
                    reverse=True,
                )
                for nb in neighbors:
                    if nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
                        if len(visited) >= limit:
                            break
            node_set = visited
        else:
            # Return all connected nodes
            node_set = set(degree.keys())

        edges = [e for e in all_edges if e["source"] in node_set and e["target"] in node_set]
        nodes_result = session.run(
            "MATCH (n:SPONode {graph_id: $graph_id}) WHERE n.node_id IN $ids RETURN n",
            graph_id=graph_id, ids=list(node_set),
        )
        nodes = [dict(r["n"]) for r in nodes_result]

    return {"nodes": nodes, "edges": edges, "graph": kg}


def list_spo_graphs(driver: Driver) -> list[dict]:
    """List all KnowledgeGraph roots."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (kg:KnowledgeGraph)
            RETURN kg ORDER BY kg.created_at DESC
            """
        )
        return [dict(r["kg"]) for r in result]


def merge_triples_into_graph(driver: Driver, graph_id: str, spo_results: list[dict]) -> int:
    """Append triples into an existing graph WITHOUT clearing previous data.

    Used for incremental / multi-doc global graph building.
    Returns number of new triples written.
    """
    written = 0
    with driver.session() as session:
        for item in spo_results:
            for t in item.get("triples", []):
                s_id = _node_id(graph_id, t["s"], t["s_type"])
                o_id = _node_id(graph_id, t["o"], t["o_type"])
                session.run(_MERGE_NODE, node_id=s_id, name=t["s"], type=t["s_type"], graph_id=graph_id)
                session.run(_MERGE_NODE, node_id=o_id, name=t["o"], type=t["o_type"], graph_id=graph_id)
                session.run(_MERGE_REL, s_id=s_id, o_id=o_id, predicate=t["p"], p_type=t["p_type"], graph_id=graph_id)
                session.run(_LINK_ROOT, graph_id=graph_id, node_id=s_id)
                session.run(_LINK_ROOT, graph_id=graph_id, node_id=o_id)
                written += 1
    return written


def ensure_global_graph(driver: Driver, graph_id: str) -> None:
    """Create the KnowledgeGraph root if it doesn't exist yet."""
    with driver.session() as session:
        session.run(
            """
            MERGE (kg:KnowledgeGraph {graph_id: $graph_id})
            ON CREATE SET kg.created_at = $ts, kg.status = 'building',
                          kg.doc_id = 'ALL', kg.chapter = 'ALL',
                          kg.node_count = 0, kg.edge_count = 0
            """,
            graph_id=graph_id, ts=int(time.time()),
        )


def update_global_graph_counts(driver: Driver, graph_id: str) -> None:
    with driver.session() as session:
        r = session.run(
            "MATCH (n:SPONode {graph_id: $gid}) RETURN count(n) AS nc", gid=graph_id
        ).single()
        r2 = session.run(
            "MATCH ()-[r:SPO_REL {graph_id: $gid}]->() RETURN count(r) AS ec", gid=graph_id
        ).single()
        session.run(
            """
            MATCH (kg:KnowledgeGraph {graph_id: $gid})
            SET kg.node_count = $nc, kg.edge_count = $ec, kg.status = 'ready'
            """,
            gid=graph_id, nc=r["nc"] if r else 0, ec=r2["ec"] if r2 else 0,
        )


def delete_spo_graph(driver: Driver, graph_id: str) -> int:
    """Delete a named SPO graph and all its SPONodes. Returns deleted node count."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (kg:KnowledgeGraph {graph_id: $graph_id})
            OPTIONAL MATCH (kg)-[:CONTAINS_NODE]->(n:SPONode)
            WITH kg, collect(n) AS nodes, count(n) AS cnt
            FOREACH (n IN nodes | DETACH DELETE n)
            DELETE kg
            RETURN cnt
            """,
            graph_id=graph_id,
        ).single()
    return result["cnt"] if result else 0
