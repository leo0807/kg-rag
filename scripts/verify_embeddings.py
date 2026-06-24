#!/usr/bin/env python3
"""
verify_embeddings.py — Check that all Milvus section IDs exist in Neo4j.

Detects orphaned vectors (in Milvus but not in Neo4j) and missing vectors
(Neo4j sections without a corresponding Milvus embedding).

Usage:
    python scripts/verify_embeddings.py
    python scripts/verify_embeddings.py --fix-orphans   # delete orphaned Milvus entries
    python scripts/verify_embeddings.py --json
"""
import argparse
import json
import os
import sys


def get_neo4j_section_ids(uri: str, user: str, password: str) -> set:
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(user, password))
    ids = set()
    with driver.session() as s:
        result = s.run("MATCH (sec:Section) WHERE sec.section_id IS NOT NULL RETURN sec.section_id AS sid")
        for r in result:
            ids.add(str(r["sid"]))
    driver.close()
    return ids


def get_milvus_section_ids(host: str, port: int, collection: str) -> set:
    from pymilvus import connections, Collection
    connections.connect(alias="verify", host=host, port=str(port))
    coll = Collection(collection)
    coll.load()
    results = coll.query(expr="section_id != ''", output_fields=["section_id"], limit=100000)
    connections.disconnect("verify")
    return {str(r["section_id"]) for r in results}


def delete_milvus_orphans(host: str, port: int, collection: str, orphan_ids: set):
    from pymilvus import connections, Collection
    connections.connect(alias="fix", host=host, port=str(port))
    coll = Collection(collection)
    ids_list = list(orphan_ids)
    expr = "section_id in [" + ",".join(f'"{sid}"' for sid in ids_list) + "]"
    coll.delete(expr)
    connections.disconnect("fix")
    return len(ids_list)


def main():
    parser = argparse.ArgumentParser(description="Verify Milvus embeddings vs Neo4j sections")
    parser.add_argument("--fix-orphans", action="store_true", help="Delete orphaned Milvus vectors")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    neo4j_uri      = os.getenv("NEO4J_URI",         "bolt://localhost:7687")
    neo4j_user     = os.getenv("NEO4J_USER",         "neo4j")
    neo4j_pass     = os.getenv("NEO4J_PASSWORD",     "password")
    milvus_host    = os.getenv("MILVUS_HOST",        "localhost")
    milvus_port    = int(os.getenv("MILVUS_PORT",    "19530"))
    milvus_coll    = os.getenv("MILVUS_COLLECTION",  "kg_sections")

    print("Fetching Neo4j section IDs ...")
    try:
        neo4j_ids = get_neo4j_section_ids(neo4j_uri, neo4j_user, neo4j_pass)
        print(f"  Neo4j sections: {len(neo4j_ids)}")
    except Exception as e:
        print(f"ERROR (Neo4j): {e}", file=sys.stderr)
        sys.exit(1)

    print("Fetching Milvus section IDs ...")
    try:
        milvus_ids = get_milvus_section_ids(milvus_host, milvus_port, milvus_coll)
        print(f"  Milvus vectors: {len(milvus_ids)}")
    except Exception as e:
        print(f"ERROR (Milvus): {e}", file=sys.stderr)
        sys.exit(1)

    orphans  = milvus_ids - neo4j_ids   # in Milvus, not in Neo4j
    missing  = neo4j_ids  - milvus_ids  # in Neo4j, not in Milvus

    report = {
        "neo4j_count":   len(neo4j_ids),
        "milvus_count":  len(milvus_ids),
        "orphan_count":  len(orphans),
        "missing_count": len(missing),
        "sample_orphans": list(orphans)[:10],
        "sample_missing": list(missing)[:10],
        "consistent":    len(orphans) == 0 and len(missing) == 0,
    }

    if args.json_out:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"\n=== Embedding Consistency Report ===")
        print(f"  Neo4j sections : {report['neo4j_count']}")
        print(f"  Milvus vectors : {report['milvus_count']}")
        print(f"  Orphaned (Milvus only): {report['orphan_count']}")
        print(f"  Missing  (Neo4j only) : {report['missing_count']}")
        if report["sample_orphans"]:
            print(f"  Sample orphans: {report['sample_orphans']}")
        if report["sample_missing"]:
            print(f"  Sample missing: {report['sample_missing']}")
        status = "CONSISTENT" if report["consistent"] else "INCONSISTENT"
        print(f"\nResult: {status}")

    if args.fix_orphans and orphans:
        print(f"\nDeleting {len(orphans)} orphaned Milvus vectors ...")
        deleted = delete_milvus_orphans(milvus_host, milvus_port, milvus_coll, orphans)
        print(f"Deleted {deleted} orphaned vectors.")

    sys.exit(0 if report["consistent"] else 1)


if __name__ == "__main__":
    main()
