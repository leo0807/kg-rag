#!/usr/bin/env python3
"""
scripts/migrate_to_es.py
将 Neo4j Section 数据 + Milvus 向量批量迁移到 Elasticsearch cps_sections 索引。

用法：
  python scripts/migrate_to_es.py            # 正式迁移
  python scripts/migrate_to_es.py --dry-run  # 仅统计，不写入
  python scripts/migrate_to_es.py --batch 200  # 指定批大小（默认500）
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 使 src 包可被导入 ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
os.environ.setdefault("NEO4J_URI",      "bolt://neo4j:7687")
os.environ.setdefault("NEO4J_USER",     "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "aviation123")
os.environ.setdefault("MILVUS_HOST",    "milvus")
os.environ.setdefault("MILVUS_PORT",    "19530")
os.environ.setdefault("ES_URL",         "http://elasticsearch:9200")


def parse_args():
    p = argparse.ArgumentParser(description="Migrate Neo4j sections → Elasticsearch")
    p.add_argument("--dry-run",  action="store_true", help="仅统计，不写入")
    p.add_argument("--batch",    type=int, default=500, help="每批写入条数（默认500）")
    p.add_argument("--skip-vec", action="store_true", help="跳过向量，仅索引文本")
    return p.parse_args()


def fetch_neo4j_sections() -> list[dict]:
    """从 Neo4j 查询所有 Section 节点及所属 Document 标题。"""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    query = """
        MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
        RETURN
            s.chunk_id  AS chunk_id,
            s.doc_id    AS doc_id,
            s.number    AS number,
            s.title     AS title,
            s.content   AS content,
            s.level     AS level,
            d.title     AS doc_title
        ORDER BY s.doc_id, s.chunk_id
    """
    with driver.session() as session:
        result = session.run(query)
        rows = [dict(r) for r in result]
    driver.close()
    return rows


def fetch_milvus_embeddings(doc_ids: list[str]) -> dict[str, list[float]]:
    """
    从 Milvus 按 doc_id 分批拉取向量，规避 offset+limit≤16384 的限制。
    返回 chunk_id → embedding 字典。
    """
    from pymilvus import Collection, connections, utility
    connections.connect(
        "default",
        host=os.environ["MILVUS_HOST"],
        port=os.environ["MILVUS_PORT"],
    )
    if not utility.has_collection("cps_sections"):
        print("  [warn] Milvus 集合 cps_sections 不存在，将跳过向量")
        return {}

    col = Collection("cps_sections")
    col.load()

    emb_map: dict[str, list[float]] = {}
    for i, doc_id in enumerate(doc_ids):
        try:
            rows = col.query(
                expr=f'doc_id == "{doc_id}"',
                output_fields=["chunk_id", "embedding"],
                limit=16000,
            )
            for r in rows:
                cid = r.get("chunk_id")
                emb = r.get("embedding")
                if cid and emb:
                    emb_map[cid] = emb
        except Exception as exc:
            print(f"  [warn] doc_id={doc_id} 向量拉取失败: {exc}")

        if (i + 1) % 50 == 0:
            print(f"    Milvus 进度: {i+1}/{len(doc_ids)} 文档，已拉取 {len(emb_map)} 条向量")

    return emb_map


def run_migration(sections: list[dict], emb_map: dict[str, list[float]], batch_size: int) -> None:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk as es_bulk

    es = Elasticsearch(os.environ["ES_URL"], request_timeout=60)
    total = len(sections)
    written = 0
    vec_hits = 0
    t0 = time.time()

    for start in range(0, total, batch_size):
        chunk = sections[start : start + batch_size]
        actions = []
        for s in chunk:
            cid = s.get("chunk_id") or ""
            doc: dict = {
                "chunk_id":   cid,
                "doc_id":     s.get("doc_id") or "",
                "number":     s.get("number") or "",
                "title":      s.get("title") or "",
                "content":    s.get("content") or "",
                "level":      int(s.get("level") or 0),
                "doc_title":  s.get("doc_title") or "",
                "page_num":   0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            emb = emb_map.get(cid)
            if emb:
                doc["embedding"] = emb
                vec_hits += 1
            actions.append({
                "_index":  "cps_sections",
                "_id":     cid,
                "_source": doc,
            })

        try:
            ok, errors = es_bulk(es, actions, raise_on_error=False, stats_only=False)
            written += ok
            if errors:
                print(f"  [warn] 批次写入错误 {len(errors)} 条")
        except Exception as exc:
            print(f"  [error] 批次写入失败: {exc}")

        elapsed = time.time() - t0
        pct = (start + len(chunk)) / total * 100
        spd = written / elapsed if elapsed > 0 else 0
        print(
            f"  进度 {start + len(chunk):>6}/{total}  ({pct:5.1f}%)  "
            f"写入={written}  有向量={vec_hits}  速度={spd:.0f}条/s  "
            f"耗时={elapsed:.0f}s"
        )

    total_elapsed = time.time() - t0
    print(f"\n✓ 迁移完成: 写入={written}, 有向量={vec_hits}/{total}, 无向量={total-vec_hits}, 耗时={total_elapsed:.1f}s")


def main():
    args = parse_args()

    print("=== Neo4j → Elasticsearch 迁移脚本 ===")
    print(f"  模式: {'dry-run（仅统计）' if args.dry_run else '正式写入'}")
    print(f"  批大小: {args.batch}")

    print("\n[1/3] 查询 Neo4j Section 节点...")
    t0 = time.time()
    sections = fetch_neo4j_sections()
    print(f"  共找到 {len(sections)} 个 Section，耗时 {time.time()-t0:.1f}s")

    if args.dry_run:
        doc_ids = {s.get("doc_id") for s in sections}
        has_content = sum(1 for s in sections if s.get("content"))
        print(f"\n  文档数:  {len(doc_ids)}")
        print(f"  有内容: {has_content}/{len(sections)}")
        print(f"\n  预计时间（假设 Milvus 200条/s + ES写入）：")
        est_milvus = len(sections) / 1000
        est_es = len(sections) / 500 * 2
        print(f"    Milvus 拉取: ~{est_milvus:.0f}s")
        print(f"    ES 写入:     ~{est_es:.0f}s")
        print(f"    合计:        ~{est_milvus + est_es:.0f}s")
        return

    emb_map: dict[str, list[float]] = {}
    if not args.skip_vec:
        print("\n[2/3] 从 Milvus 按文档分批拉取向量...")
        t0 = time.time()
        doc_ids = sorted({s.get("doc_id") or "" for s in sections if s.get("doc_id")})
        try:
            emb_map = fetch_milvus_embeddings(doc_ids)
            print(f"  共拉取 {len(emb_map)} 条向量（{len(doc_ids)} 个文档），耗时 {time.time()-t0:.1f}s")
        except Exception as exc:
            print(f"  [warn] Milvus 拉取失败，继续纯文本迁移: {exc}")
    else:
        print("\n[2/3] 跳过向量（--skip-vec）")

    print(f"\n[3/3] 批量写入 Elasticsearch（批大小={args.batch}）...")
    run_migration(sections, emb_map, args.batch)


if __name__ == "__main__":
    main()
