#!/usr/bin/env python3
"""
reparse_zero_section_docs.py
对 Neo4j 中 0 章节的文档重新解析并写入。

运行方式（在 backend/ 目录下）：
  python ../scripts/reparse_zero_section_docs.py
"""
import logging
import os
import sys
import tempfile
from pathlib import Path

# ── 把 backend/ 加入 sys.path ─────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aviation123")
MINIO_ENDPOINT = os.getenv("STORAGE_ENDPOINT",   "http://localhost:9000")
MINIO_KEY      = os.getenv("STORAGE_ACCESS_KEY", "minioadmin")
MINIO_SECRET   = os.getenv("STORAGE_SECRET_KEY", "minioadmin")
BUCKET_RAW     = "raw-documents"


def main():
    from neo4j import GraphDatabase
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError

    from src.services.parser import parse
    # 不导入 write_document（会拉入 pymilvus/marshmallow 冲突链）
    # 只写入 Neo4j Section 节点

    neo4j = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_KEY,
        aws_secret_access_key=MINIO_SECRET,
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

    # ── 查询 0 章节的文档 ────────────────────────────────────────────────────
    log.info("查询 Neo4j 中 0 章节的文档...")
    with neo4j.session() as s:
        rows = list(s.run("""
            MATCH (d:Document)
            WHERE NOT (d)-[:HAS_SECTION]->(:Section)
              AND d.title IS NOT NULL
            RETURN d.name AS doc_id, d.storage_key AS storage_key
            ORDER BY d.name
        """))

    total = len(rows)
    log.info("找到 %d 个 0 章节文档", total)

    ok = failed = still_zero = 0
    still_zero_list: list[str] = []
    fail_list: list[str] = []

    section_before = _count_sections(neo4j)
    log.info("修复前 Section 总数: %d", section_before)

    for idx, row in enumerate(rows, 1):
        doc_id      = row["doc_id"]
        storage_key = row["storage_key"]

        print(f"\r  [{idx:3d}/{total}] {doc_id:<15}", end="", flush=True)

        if not storage_key:
            log.warning("\n  %s 没有 storage_key，跳过", doc_id)
            fail_list.append(f"{doc_id}: 无 storage_key")
            failed += 1
            continue

        suffix = Path(storage_key).suffix or ".pdf"
        tmp_path = Path(tempfile.gettempdir()) / f"{doc_id}{suffix}"
        try:
            # 下载
            s3.download_file(BUCKET_RAW, storage_key, str(tmp_path))

            # 解析
            doc = parse(tmp_path)
            if not doc.sections:
                log.warning("\n  %s 解析后仍然 0 章节", doc_id)
                still_zero += 1
                still_zero_list.append(doc_id)
                continue

            # 只写入 Neo4j Section 节点（绕过 pymilvus/ES 依赖冲突）
            _write_sections_neo4j(neo4j, doc)
            ok += 1

        except ClientError as e:
            code = e.response["Error"]["Code"]
            log.warning("\n  %s MinIO 下载失败 (%s): %s", doc_id, code, storage_key)
            fail_list.append(f"{doc_id}: MinIO {code} key={storage_key}")
            failed += 1
        except Exception as e:
            log.warning("\n  %s 解析/写入失败: %s", doc_id, e)
            fail_list.append(f"{doc_id}: {e}")
            failed += 1
        finally:
            tmp_path.unlink(missing_ok=True)

    print()
    neo4j.close()

    section_after = _count_sections_direct()

    # ── 报告 ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("重新解析完成报告")
    print("=" * 60)
    print(f"  目标文档总数:     {total}")
    print(f"  成功修复:         {ok}")
    print(f"  解析后仍 0 章节:  {still_zero}")
    print(f"  失败（跳过）:     {failed}")
    print(f"  Section 节点变化: {section_before} → {section_after}（+{section_after - section_before}）")

    if still_zero_list:
        print(f"\n仍然 0 章节的文档（{len(still_zero_list)} 个）:")
        for d in still_zero_list:
            print(f"  - {d}")

    if fail_list:
        print(f"\n失败文档（{len(fail_list)} 个）:")
        for f in fail_list:
            print(f"  - {f}")

    print("=" * 60)


def _write_sections_neo4j(driver, doc) -> None:
    """只将 Section 节点写入 Neo4j，绕过 pymilvus / ES 依赖链。"""
    sections_data = [
        {
            "chunk_id": s.chunk_id,
            "number":   s.number,
            "title":    s.title,
            "content":  s.content,
            "page_idx": getattr(s, "page_idx", None),
            "bbox":     getattr(s, "bbox", None),
        }
        for s in doc.sections
    ]
    with driver.session() as s:
        s.run(
            """
            MATCH (d:Document {name: $doc_id})
            UNWIND $sections AS sec
            MERGE (n:Section {chunk_id: sec.chunk_id})
            SET n.doc_id   = $doc_id,
                n.number   = sec.number,
                n.title    = sec.title,
                n.content  = sec.content,
                n.page_idx = sec.page_idx,
                n.bbox     = sec.bbox
            MERGE (d)-[:HAS_SECTION]->(n)
            """,
            doc_id=doc.doc_id,
            sections=sections_data,
        )


def _count_sections(driver) -> int:
    with driver.session() as s:
        r = s.run("MATCH (s:Section) RETURN count(s) AS n").single()
        return r["n"] if r else 0


def _count_sections_direct() -> int:
    """写入完成后用新连接计数，避免缓存影响。"""
    from neo4j import GraphDatabase
    d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with d.session() as s:
            r = s.run("MATCH (s:Section) RETURN count(s) AS n").single()
            return r["n"] if r else 0
    finally:
        d.close()


if __name__ == "__main__":
    main()
