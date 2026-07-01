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

        # 2. Remove previously generated SPO nodes for this graph (rebuild)
        session.run(
            """
            MATCH (kg:KnowledgeGraph {graph_id: $graph_id})-[:CONTAINS_NODE]->(n:SPONode)
            DETACH DELETE n
            """,
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


def get_spo_graph_data(driver: Driver, graph_id: str) -> dict:
    """Return all SPONode + SPO_REL for frontend visualization."""
    with driver.session() as session:
        kg_result = session.run(
            "MATCH (kg:KnowledgeGraph {graph_id: $graph_id}) RETURN kg",
            graph_id=graph_id,
        ).single()
        if not kg_result:
            return {"nodes": [], "edges": [], "graph": None}

        kg = dict(kg_result["kg"])

        nodes_result = session.run(
            "MATCH (n:SPONode {graph_id: $graph_id}) RETURN n",
            graph_id=graph_id,
        )
        nodes = [dict(r["n"]) for r in nodes_result]

        edges_result = session.run(
            """
            MATCH (s:SPONode {graph_id: $graph_id})-[r:SPO_REL {graph_id: $graph_id}]->(o:SPONode)
            RETURN s.node_id AS source, o.node_id AS target,
                   r.predicate AS predicate, r.predicate_type AS predicate_type
            """,
            graph_id=graph_id,
        )
        edges = [dict(r) for r in edges_result]

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
