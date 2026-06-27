#!/usr/bin/env python3
"""
Neo4j GDS analytics: PageRank, Louvain, NodeSimilarity, Betweenness Centrality.

Writes results back as node properties; NodeSimilarity also creates SIMILAR_TO edges.
Can be run standalone or called from Airflow DAG (graph_analytics.py).

Usage:
    pip install neo4j
    python scripts/run_gds_analytics.py \
        [--neo4j-uri bolt://localhost:7687] \
        [--neo4j-password password] \
        [--algorithms pagerank louvain similarity betweenness] \
        [--dry-run]

Algorithms:
    pagerank     — Compute chapter importance; writes Section.pagerank
    louvain      — Community detection; writes Section.community_id
    similarity   — Node similarity; creates SIMILAR_TO edges (threshold 0.7)
    betweenness  — Identify bridge nodes; writes Section.betweenness

Neo4j GDS plugin required:
    Add to neo4j.conf: dbms.security.procedures.unrestricted=gds.*
    Or install via: neo4j-admin plugins install graph-data-science
"""
from __future__ import annotations

import argparse
import logging
import os

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

GRAPH_NAME   = "sectionGraph"
MIN_SIM      = float(os.getenv("GDS_SIMILARITY_THRESHOLD", "0.7"))
TOP_K_SIM    = int(os.getenv("GDS_SIMILARITY_TOPK", "10"))
DAMPING      = float(os.getenv("GDS_PAGERANK_DAMPING", "0.85"))
MAX_ITER_PR  = int(os.getenv("GDS_PAGERANK_ITER", "20"))


def _project_graph(session) -> None:
    """Project Section nodes + their relationships into GDS in-memory graph."""
    try:
        session.run(f"CALL gds.graph.drop('{GRAPH_NAME}', false)")
    except Exception:
        pass

    session.run(
        f"""
        CALL gds.graph.project(
            '{GRAPH_NAME}',
            'Section',
            {{
                REFERENCES:   {{orientation: 'NATURAL'}},
                HAS_TOPIC:    {{orientation: 'NATURAL'}},
                NEXT_SECTION: {{orientation: 'NATURAL'}}
            }},
            {{
                nodeProperties: ['pagerank', 'heat_score']
            }}
        )
        """
    )
    log.info("GDS graph projected: %s", GRAPH_NAME)


def run_pagerank(session) -> int:
    result = session.run(
        f"""
        CALL gds.pageRank.write('{GRAPH_NAME}', {{
            maxIterations:     {MAX_ITER_PR},
            dampingFactor:     {DAMPING},
            writeProperty:    'pagerank',
            scaler:            'MinMax'
        }})
        YIELD nodePropertiesWritten, ranIterations
        RETURN nodePropertiesWritten, ranIterations
        """
    )
    row = result.single()
    written = row["nodePropertiesWritten"]
    log.info("PageRank: wrote to %d nodes (%d iterations)", written, row["ranIterations"])
    return written


def run_louvain(session) -> int:
    result = session.run(
        f"""
        CALL gds.louvain.write('{GRAPH_NAME}', {{
            writeProperty: 'community_id',
            includeIntermediateCommunities: false
        }})
        YIELD nodePropertiesWritten, communityCount
        RETURN nodePropertiesWritten, communityCount
        """
    )
    row = result.single()
    written = row["nodePropertiesWritten"]
    log.info("Louvain: %d communities detected, wrote to %d nodes",
             row["communityCount"], written)
    return written


def run_node_similarity(session) -> int:
    """Compute node similarity and write SIMILAR_TO edges."""
    result = session.run(
        f"""
        CALL gds.nodeSimilarity.write('{GRAPH_NAME}', {{
            writeRelationshipType: 'SIMILAR_TO',
            writeProperty:         'similarity',
            similarityCutoff:      {MIN_SIM},
            topK:                  {TOP_K_SIM},
            degreeCutoff:          1
        }})
        YIELD nodesCompared, relationshipsWritten
        RETURN nodesCompared, relationshipsWritten
        """
    )
    row = result.single()
    log.info("NodeSimilarity: compared %d nodes, wrote %d SIMILAR_TO edges (cutoff=%.2f)",
             row["nodesCompared"], row["relationshipsWritten"], MIN_SIM)
    return row["relationshipsWritten"]


def run_betweenness(session) -> int:
    result = session.run(
        f"""
        CALL gds.betweenness.write('{GRAPH_NAME}', {{
            writeProperty: 'betweenness',
            samplingSize:  1000
        }})
        YIELD nodePropertiesWritten, centralityDistribution
        RETURN nodePropertiesWritten, centralityDistribution
        """
    )
    row = result.single()
    dist = row.get("centralityDistribution", {})
    log.info(
        "Betweenness: wrote to %d nodes (max=%.2f, mean=%.2f)",
        row["nodePropertiesWritten"],
        dist.get("max", 0),
        dist.get("mean", 0),
    )
    return row["nodePropertiesWritten"]


def _drop_graph(session) -> None:
    try:
        session.run(f"CALL gds.graph.drop('{GRAPH_NAME}', false)")
    except Exception:
        pass


def run_analytics(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    algorithms: list[str],
    dry_run: bool,
) -> dict[str, int]:
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    results: dict[str, int] = {}

    with driver.session() as session:
        if dry_run:
            log.info("[dry-run] Would run GDS algorithms: %s on %s", algorithms, neo4j_uri)
            return {a: 0 for a in algorithms}

        _project_graph(session)
        try:
            if "pagerank" in algorithms:
                results["pagerank"] = run_pagerank(session)
            if "louvain" in algorithms:
                results["louvain"] = run_louvain(session)
            if "similarity" in algorithms:
                results["similarity"] = run_node_similarity(session)
            if "betweenness" in algorithms:
                results["betweenness"] = run_betweenness(session)
        finally:
            _drop_graph(session)

    driver.close()
    return results


def main() -> None:
    ALL = ["pagerank", "louvain", "similarity", "betweenness"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri",      default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user",     default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--algorithms",     nargs="+", default=ALL, choices=ALL,
                        metavar="ALG", help=f"One or more of: {ALL}")
    parser.add_argument("--dry-run",        action="store_true")
    args = parser.parse_args()

    results = run_analytics(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        algorithms=args.algorithms,
        dry_run=args.dry_run,
    )

    print("\nGDS analytics summary:")
    for alg, count in results.items():
        print(f"  {alg}: {count} nodes/edges updated")


if __name__ == "__main__":
    main()
