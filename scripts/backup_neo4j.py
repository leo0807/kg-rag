#!/usr/bin/env python3
"""
backup_neo4j.py — Export Neo4j graph data to a timestamped JSON backup.

Exports: Document, Section, Entity nodes and their relationships.

Usage:
    python scripts/backup_neo4j.py
    python scripts/backup_neo4j.py --output-dir /data/backups
    python scripts/backup_neo4j.py --dry-run
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def connect(uri: str, user: str, password: str):
    from neo4j import GraphDatabase
    return GraphDatabase.driver(uri, auth=(user, password))


def export_nodes(session, label: str) -> list:
    result = session.run(f"MATCH (n:{label}) RETURN properties(n) AS props, id(n) AS nid")
    return [{"_id": r["nid"], **r["props"]} for r in result]


def export_relationships(session, rel_type: str) -> list:
    result = session.run(
        f"MATCH (a)-[r:{rel_type}]->(b) "
        "RETURN id(a) AS src, id(b) AS tgt, properties(r) AS props"
    )
    return [{"src": r["src"], "tgt": r["tgt"], **r["props"]} for r in result]


def main():
    parser = argparse.ArgumentParser(description="Backup Neo4j graph to JSON")
    parser.add_argument("--output-dir", default="./backups", help="Directory for backup files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be exported, no file written")
    args = parser.parse_args()

    uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user     = os.getenv("NEO4J_USER",     "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    print(f"Connecting to Neo4j at {uri} ...")
    try:
        driver = connect(uri, user, password)
    except Exception as e:
        print(f"ERROR: Cannot connect to Neo4j: {e}", file=sys.stderr)
        sys.exit(1)

    data = {}
    with driver.session() as session:
        for label in ("Document", "Section", "Tool", "Material", "Process", "Constraint"):
            nodes = export_nodes(session, label)
            data[f"nodes_{label}"] = nodes
            print(f"  Exported {len(nodes):>6} {label} nodes")

        for rel in ("HAS_SECTION", "MENTIONED_IN", "REFERENCES", "RELATED_TO"):
            rels = export_relationships(session, rel)
            data[f"rels_{rel}"] = rels
            print(f"  Exported {len(rels):>6} {rel} relationships")

    driver.close()

    total_nodes = sum(len(v) for k, v in data.items() if k.startswith("nodes_"))
    total_rels  = sum(len(v) for k, v in data.items() if k.startswith("rels_"))
    print(f"\nTotal: {total_nodes} nodes, {total_rels} relationships")

    if args.dry_run:
        print("[dry-run] No file written.")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"neo4j_backup_{timestamp}.json"

    out_path.write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2))
    print(f"\nBackup written to: {out_path}")
    print(f"File size: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
