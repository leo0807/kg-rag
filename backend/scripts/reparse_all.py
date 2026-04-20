"""
scripts/reparse_all.py
批量重新解析所有文档（Neo4j only，跳过 Milvus/ES）

用法：
    cd backend/
    python scripts/reparse_all.py

支持断点续跑：进度记录到 /tmp/reparse_progress.json，
重新运行时跳过已成功的 doc_id。
"""
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logging import setup_logging
from src.core.database import init_db, get_driver

setup_logging()
logger = logging.getLogger(__name__)

PROGRESS_FILE = Path("/tmp/reparse_progress.json")


# ── 进度持久化 ───────────────────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {"done": [], "failed": {}}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2))


# ── Neo4j 写入（仅节点，不含向量/ES）───────────────────────────────────────

def neo4j_rewrite_sections(driver, doc_id: str, sections: list) -> int:
    """删除旧 Section 并写入新 Section，重建层级和顺序关系。"""
    if not sections:
        return 0
    sections_data = [
        {"chunk_id": s["chunk_id"], "number": s["number"], "title": s["title"],
         "content": s["content"], "level": s["level"], "seq_index": s["seq_index"]}
        for s in sections
    ]
    with driver.session() as session:
        session.run(
            "MATCH (d:Document {name:$d})-[:HAS_SECTION]->(s:Section) DETACH DELETE s",
            d=doc_id,
        )
        session.run(
            """
            MATCH (d:Document {name: $doc_id})
            UNWIND $sections AS s
            MERGE (sec:Section {chunk_id: s.chunk_id})
            SET sec.doc_id    = $doc_id,
                sec.number    = s.number,
                sec.title     = s.title,
                sec.content   = s.content,
                sec.level     = s.level,
                sec.seq_index = s.seq_index
            MERGE (d)-[:HAS_SECTION]->(sec)
            """,
            doc_id=doc_id,
            sections=sections_data,
        )
        # 层级关系
        n2c = {s["number"]: s["chunk_id"] for s in sections}
        parent_pairs = []
        for s in sections:
            parts = s["number"].split(".")
            if len(parts) > 1:
                parent_num = ".".join(parts[:-1])
                if parent_num in n2c:
                    parent_pairs.append({"parent_id": n2c[parent_num], "child_id": s["chunk_id"]})
        if parent_pairs:
            session.run(
                "UNWIND $p AS p "
                "MATCH (a:Section{chunk_id:p.parent_id}) MATCH (b:Section{chunk_id:p.child_id}) "
                "MERGE (a)-[:HAS_SUBSECTION]->(b)",
                p=parent_pairs,
            )
        # 顺序关系
        next_pairs = [
            {"from_id": sections[i]["chunk_id"], "to_id": sections[i + 1]["chunk_id"]}
            for i in range(len(sections) - 1)
        ]
        if next_pairs:
            session.run(
                "UNWIND $p AS p "
                "MATCH (a:Section{chunk_id:p.from_id}) MATCH (b:Section{chunk_id:p.to_id}) "
                "MERGE (a)-[:NEXT_SECTION]->(b)",
                p=next_pairs,
            )
    return len(sections)


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def main():
    init_db()
    driver = get_driver()

    # 获取所有文档
    with driver.session() as s:
        rows = list(s.run("MATCH (d:Document) RETURN d.name AS doc_id, d.storage_key AS sk"))
    docs = [(r["doc_id"], r["sk"]) for r in rows if r["doc_id"]]
    logger.info("总文档数: %d", len(docs))

    # 修复前统计
    with driver.session() as s:
        before_total = s.run("MATCH (s:Section) RETURN count(s) AS n").single()["n"]
        before_levels = {
            r["level"]: r["cnt"]
            for r in s.run("MATCH (s:Section) RETURN s.level AS level, count(s) AS cnt ORDER BY level")
        }
    logger.info("修复前 Section 总数: %d  分布: %s", before_total, before_levels)

    progress = load_progress()
    done_set = set(progress["done"])
    failed_map: dict = progress["failed"]

    from src.core.storage import download_bytes, BUCKET_RAW_DOCUMENTS
    from src.services.parser import parse
    from src.services.docx_parser import parse_docx

    ok_count = 0
    fail_count = 0
    skip_count = len(done_set)
    total = len(docs)

    for idx, (doc_id, storage_key) in enumerate(docs, 1):
        if doc_id in done_set:
            continue  # 断点续跑：跳过已完成

        if not storage_key:
            logger.warning("[%d/%d] %s: 无 storage_key，跳过", idx, total, doc_id)
            failed_map[doc_id] = "no storage_key"
            fail_count += 1
            save_progress({"done": list(done_set), "failed": failed_map})
            continue

        suffix = Path(storage_key).suffix.lower()
        tmp_path = Path(f"/tmp/{doc_id}_reparse{suffix}")

        try:
            # 1. 下载
            raw = download_bytes(BUCKET_RAW_DOCUMENTS, storage_key)
            tmp_path.write_bytes(raw)

            # 2. 解析
            if suffix == ".docx":
                doc_schema = parse_docx(tmp_path)
                sections = [
                    {"chunk_id": s.chunk_id, "number": s.number, "title": s.title,
                     "content": s.content, "level": s.level, "seq_index": s.seq_index}
                    for s in doc_schema.sections
                ]
            else:
                # .pdf / .doc（parse 内部处理 .doc → .docx 转换）
                doc_result = parse(tmp_path)
                if hasattr(doc_result, "sections"):
                    # DocumentSchema object
                    sections = [
                        {"chunk_id": s.chunk_id, "number": s.number, "title": s.title,
                         "content": s.content, "level": s.level, "seq_index": s.seq_index}
                        for s in doc_result.sections
                    ]
                else:
                    # dict（older return format）
                    sections = doc_result.get("sections", [])
                    if sections and hasattr(sections[0], "chunk_id"):
                        sections = [
                            {"chunk_id": s.chunk_id, "number": s.number, "title": s.title,
                             "content": s.content, "level": s.level, "seq_index": s.seq_index}
                            for s in sections
                        ]

            if not sections:
                logger.warning("[%d/%d] %s: 解析结果为空，跳过写入", idx, total, doc_id)
                failed_map[doc_id] = "empty sections"
                fail_count += 1
                save_progress({"done": list(done_set), "failed": failed_map})
                continue

            # 3. 写 Neo4j
            n = neo4j_rewrite_sections(driver, doc_id, sections)

            done_set.add(doc_id)
            ok_count += 1

            if idx % 10 == 0 or idx == total:
                save_progress({"done": list(done_set), "failed": failed_map})
                logger.info(
                    "进度 [%d/%d]  已完成=%d  失败=%d  跳过=%d  最新: %s (%d 节)",
                    idx, total, ok_count, fail_count, skip_count, doc_id, n,
                )

        except Exception as e:
            logger.warning("[%d/%d] %s: ERROR %s", idx, total, doc_id, e)
            failed_map[doc_id] = str(e)[:200]
            fail_count += 1
            save_progress({"done": list(done_set), "failed": failed_map})

        finally:
            tmp_path.unlink(missing_ok=True)

    # 最终统计
    save_progress({"done": list(done_set), "failed": failed_map})

    with driver.session() as s:
        after_total = s.run("MATCH (s:Section) RETURN count(s) AS n").single()["n"]
        after_levels = {
            r["level"]: r["cnt"]
            for r in s.run("MATCH (s:Section) RETURN s.level AS level, count(s) AS cnt ORDER BY level")
        }

    print("\n" + "=" * 60)
    print(f"批量重新解析完成")
    print(f"  成功: {ok_count + skip_count}  (本次新处理: {ok_count}, 已跳过: {skip_count})")
    print(f"  失败: {fail_count}")
    print(f"\n  修复前 Section 总数: {before_total}")
    print(f"  修复后 Section 总数: {after_total}")
    print(f"  差值: {after_total - before_total:+d}")
    print(f"\n  修复前层级分布: {before_levels}")
    print(f"  修复后层级分布: {after_levels}")
    if failed_map:
        print(f"\n  失败文档 ({len(failed_map)} 个):")
        for d, err in list(failed_map.items())[:20]:
            print(f"    {d}: {err[:80]}")
    print("=" * 60)

    driver.close()


if __name__ == "__main__":
    main()
