#!/usr/bin/env python3
"""
Batch-migrate Neo4j Section nodes → OpenSearch (ES-compatible) index.

Neo4j retains the graph structure; OpenSearch handles full-text + vector search.
Existing ES index (cps_sections) is reused if already present.

Usage:
    pip install neo4j elasticsearch tqdm
    python scripts/migrate_to_opensearch.py \
        [--neo4j-uri bolt://localhost:7687] \
        [--neo4j-user neo4j] \
        [--neo4j-password password] \
        [--es-url http://localhost:9200] \
        [--batch-size 256] \
        [--embed]          # also generate BGE-M3 embeddings (requires GPU)
        [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

INDEX_NAME = "cps_sections"
EMBEDDING_DIMS = 1024


def _neo4j_sections(driver, skip: int, limit: int) -> list[dict]:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (s:Section)
            RETURN s.chunk_id AS chunk_id,
                   s.doc_id AS doc_id,
                   s.section_number AS number,
                   s.title AS title,
                   s.content AS content,
                   s.level AS level,
                   s.doc_title AS doc_title,
                   s.page_num AS page_num
            ORDER BY s.chunk_id
            SKIP $skip LIMIT $limit
            """,
            skip=skip, limit=limit,
        )
        return [dict(r) for r in result]


def _ensure_index(es) -> None:
    """Create OpenSearch index if missing; add sparse_vector field for SPLADE."""
    if es.indices.exists(index=INDEX_NAME):
        log.info("Index already exists: %s", INDEX_NAME)
        return

    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "ik_index":  {"type": "custom", "tokenizer": "ik_max_word"},
                    "ik_search": {"type": "custom", "tokenizer": "ik_smart"},
                }
            },
        },
        "mappings": {
            "properties": {
                "chunk_id":      {"type": "keyword"},
                "doc_id":        {"type": "keyword"},
                "number":        {"type": "keyword"},
                "title":         {"type": "text", "analyzer": "ik_index", "search_analyzer": "ik_search"},
                "content":       {"type": "text", "analyzer": "ik_index", "search_analyzer": "ik_search"},
                "level":         {"type": "integer"},
                "doc_title":     {"type": "text"},
                "page_num":      {"type": "integer"},
                "created_at":    {"type": "date"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMS,
                    "index": True,
                    "similarity": "cosine",
                },
                "splade_vector": {
                    "type": "sparse_vector",  # OpenSearch 2.x / ES 8.11+
                },
            }
        },
    }
    try:
        es.indices.create(index=INDEX_NAME, body=mapping)
        log.info("Index created with IK analyzer and sparse_vector field")
    except Exception as exc:
        if "ik" in str(exc).lower() or "analyzer" in str(exc).lower():
            del mapping["settings"]["analysis"]
            es.indices.create(index=INDEX_NAME, body=mapping)
            log.warning("IK analyzer not available — created with standard tokenizer")
        else:
            raise


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate BGE-M3 embeddings; returns empty list on failure."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))
        from services.retrieval.embedder import embed_texts
        return embed_texts(texts)
    except Exception as exc:
        log.warning("Embedding failed (--embed skipped for this batch): %s", exc)
        return []


def migrate(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    es_url: str,
    batch_size: int,
    do_embed: bool,
    dry_run: bool,
) -> None:
    from neo4j import GraphDatabase
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk as es_bulk

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    es = Elasticsearch(es_url, request_timeout=60)

    if not dry_run:
        _ensure_index(es)

    skip = 0
    total = 0
    while True:
        rows = _neo4j_sections(driver, skip, batch_size)
        if not rows:
            break

        embeddings: list[list[float]] = []
        if do_embed:
            texts = [r.get("content") or r.get("title") or "" for r in rows]
            embeddings = _embed_batch(texts)

        actions = []
        for i, row in enumerate(rows):
            doc = {
                "chunk_id":   row.get("chunk_id", ""),
                "doc_id":     row.get("doc_id", ""),
                "number":     row.get("number", ""),
                "title":      row.get("title", ""),
                "content":    row.get("content", ""),
                "level":      row.get("level") or 1,
                "doc_title":  row.get("doc_title", ""),
                "page_num":   row.get("page_num") or 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            if embeddings and i < len(embeddings):
                doc["embedding"] = embeddings[i]

            actions.append({
                "_index": INDEX_NAME,
                "_id":    row["chunk_id"],
                "_source": doc,
            })

        if dry_run:
            log.info("[dry-run] Would index %d docs (skip=%d)", len(actions), skip)
        else:
            success, errors = es_bulk(es, actions, raise_on_error=False)
            if errors:
                log.warning("%d bulk errors in batch skip=%d", len(errors), skip)
            log.info("Indexed %d/%d sections (skip=%d)", success, len(rows), skip)

        total += len(rows)
        skip += batch_size

    driver.close()
    log.info("Migration complete: %d sections total", total)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neo4j-uri",      default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user",     default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--es-url",         default=os.getenv("ES_URL", "http://localhost:9200"))
    parser.add_argument("--batch-size",     type=int, default=256)
    parser.add_argument("--embed",          action="store_true",
                        help="Generate BGE-M3 embeddings (requires model loaded)")
    parser.add_argument("--dry-run",        action="store_true")
    args = parser.parse_args()

    migrate(
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        es_url=args.es_url,
        batch_size=args.batch_size,
        do_embed=args.embed,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
