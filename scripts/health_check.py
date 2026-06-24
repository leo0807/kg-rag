#!/usr/bin/env python3
"""
health_check.py — Check all external dependencies and report status.

Usage:
    python scripts/health_check.py
    python scripts/health_check.py --json
"""
import argparse
import json
import os
import sys
import time

# ── Neo4j ─────────────────────────────────────────────────────────────────────
def check_neo4j(uri: str, user: str, password: str) -> dict:
    start = time.time()
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as s:
            s.run("RETURN 1").single()
        driver.close()
        return {"status": "ok", "latency_ms": round((time.time() - start) * 1000, 1)}
    except Exception as e:
        return {"status": "down", "error": str(e)[:120],
                "latency_ms": round((time.time() - start) * 1000, 1)}


# ── Milvus ────────────────────────────────────────────────────────────────────
def check_milvus(host: str, port: int) -> dict:
    start = time.time()
    try:
        from pymilvus import connections, utility
        connections.connect(alias="health_check", host=host, port=str(port))
        utility.list_collections()
        connections.disconnect("health_check")
        return {"status": "ok", "latency_ms": round((time.time() - start) * 1000, 1)}
    except Exception as e:
        return {"status": "down", "error": str(e)[:120],
                "latency_ms": round((time.time() - start) * 1000, 1)}


# ── Elasticsearch ─────────────────────────────────────────────────────────────
def check_elasticsearch(url: str) -> dict:
    start = time.time()
    try:
        from elasticsearch import Elasticsearch
        es = Elasticsearch(url)
        if not es.ping():
            raise ConnectionError("ping returned False")
        return {"status": "ok", "latency_ms": round((time.time() - start) * 1000, 1)}
    except Exception as e:
        return {"status": "down", "error": str(e)[:120],
                "latency_ms": round((time.time() - start) * 1000, 1)}


# ── Redis ─────────────────────────────────────────────────────────────────────
def check_redis(url: str) -> dict:
    start = time.time()
    try:
        import redis
        r = redis.from_url(url, decode_responses=True, socket_timeout=3)
        r.ping()
        return {"status": "ok", "latency_ms": round((time.time() - start) * 1000, 1)}
    except Exception as e:
        return {"status": "down", "error": str(e)[:120],
                "latency_ms": round((time.time() - start) * 1000, 1)}


def main():
    parser = argparse.ArgumentParser(description="Check all external dependencies")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    neo4j_uri  = os.getenv("NEO4J_URI",  "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_pass = os.getenv("NEO4J_PASSWORD", "password")
    milvus_host = os.getenv("MILVUS_HOST", "localhost")
    milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
    es_url     = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    redis_url  = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    results = {
        "neo4j":         check_neo4j(neo4j_uri, neo4j_user, neo4j_pass),
        "milvus":        check_milvus(milvus_host, milvus_port),
        "elasticsearch": check_elasticsearch(es_url),
        "redis":         check_redis(redis_url),
    }

    all_ok = all(v["status"] == "ok" for v in results.values())

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("\n=== Dependency Health Check ===")
        for name, info in results.items():
            icon = "✓" if info["status"] == "ok" else "✗"
            latency = f"{info['latency_ms']}ms"
            err = f" — {info.get('error', '')}" if info["status"] != "ok" else ""
            print(f"  {icon} {name:<20} {latency}{err}")
        print(f"\nOverall: {'OK' if all_ok else 'DEGRADED'}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
