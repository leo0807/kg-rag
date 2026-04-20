"""
scripts/backfill_tables.py
为已入库但缺少 HAS_TABLE 关系的文档补全表格数据。

用法：
    cd backend/
    python scripts/backfill_tables.py [--dry-run]

功能：
    1. 查询 Neo4j 中没有 HAS_TABLE 关系的 Document
    2. 从 MinIO 下载原始 PDF
    3. 用 pdfplumber 提取表格写入 Neo4j
    4. 显示进度，单个失败跳过继续
"""
import argparse
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.logging import setup_logging
from src.core.database import init_db, get_driver
from src.core import storage
from src.services.parser import extract_sections, extract_tables_pdfplumber
from src.services.entity_writer import write_tables

setup_logging()
logger = logging.getLogger(__name__)


def get_docs_without_tables(driver) -> list[dict]:
    """返回没有任何 HAS_TABLE 关系的文档列表。"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            WHERE NOT (d)-[:HAS_SECTION]->(:Section)-[:HAS_TABLE]->(:Table)
            RETURN d.name AS doc_id, d.title AS title
            ORDER BY d.name
        """)
        return [{"doc_id": r["doc_id"], "title": r["title"] or ""} for r in result]


def get_sections_for_doc(driver, doc_id: str) -> list[dict]:
    """从 Neo4j 取已解析的 Section（含 page_idx，用于表格关联）。"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id AS chunk_id, s.number AS number,
                   coalesce(s.page_idx, 0) AS page_idx
            ORDER BY s.seq_index
        """, doc_id=doc_id)
        return [dict(r) for r in result]


def download_pdf(doc_id: str) -> Path | None:
    """从 MinIO 下载原始 PDF，返回临时文件路径；失败返回 None。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        # 尝试两种常见键格式
        for key in [f"{doc_id}.pdf", f"{doc_id.lower()}.pdf"]:
            try:
                data = storage.download_bytes(storage.BUCKET_RAW_DOCUMENTS, key)
                tmp_path.write_bytes(data)
                return tmp_path
            except Exception:
                continue
        # 列出 bucket 前缀匹配
        for key in storage.list_files(storage.BUCKET_RAW_DOCUMENTS, prefix=doc_id):
            if key.lower().endswith(".pdf"):
                data = storage.download_bytes(storage.BUCKET_RAW_DOCUMENTS, key)
                tmp_path.write_bytes(data)
                return tmp_path
        return None
    except Exception as e:
        logger.warning("下载 %s 失败: %s", doc_id, e)
        return None


def backfill_one(driver, doc_id: str, dry_run: bool = False) -> int:
    """
    为单个文档补全表格。返回写入的表格数量（0 表示无表格或失败）。
    """
    pdf_path = download_pdf(doc_id)
    if not pdf_path:
        logger.warning("[%s] 未找到原始 PDF，跳过", doc_id)
        return 0

    try:
        # 从 Neo4j 取已解析的 sections（用于 page→chunk 映射）
        sections = get_sections_for_doc(driver, doc_id)
        if not sections:
            logger.warning("[%s] Neo4j 中无 Section，跳过", doc_id)
            return 0

        tables = extract_tables_pdfplumber(pdf_path, doc_id, sections)
        if not tables:
            logger.info("[%s] 无可提取的表格", doc_id)
            return 0

        if dry_run:
            logger.info("[%s] DRY-RUN: 发现 %d 个表格", doc_id, len(tables))
            return len(tables)

        write_tables(driver, doc_id, tables)
        logger.info("[%s] 写入 %d 个表格", doc_id, len(tables))
        return len(tables)

    except Exception as e:
        logger.error("[%s] 处理失败: %s", doc_id, e, exc_info=True)
        return 0
    finally:
        try:
            pdf_path.unlink()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="为缺少表格数据的文档补全表格")
    parser.add_argument("--dry-run", action="store_true", help="只检测，不写入 Neo4j")
    parser.add_argument("--doc-id", help="只处理指定文档（留空处理所有）")
    args = parser.parse_args()

    init_db()
    driver = get_driver()

    if args.doc_id:
        docs = [{"doc_id": args.doc_id, "title": ""}]
    else:
        docs = get_docs_without_tables(driver)

    total = len(docs)
    if total == 0:
        print("所有文档已有表格数据，无需补全。")
        return

    print(f"发现 {total} 个文档需要补全表格数据{'（DRY-RUN）' if args.dry_run else ''}")

    ok = skipped = tables_total = 0
    for i, doc in enumerate(docs, 1):
        doc_id = doc["doc_id"]
        print(f"[{i}/{total}] {doc_id} {doc['title'][:30]}", end="  ", flush=True)
        n = backfill_one(driver, doc_id, dry_run=args.dry_run)
        if n > 0:
            print(f"✓ {n} 表格")
            ok += 1
            tables_total += n
        else:
            print("— 跳过")
            skipped += 1

    print(f"\n完成：{ok} 个文档写入 {tables_total} 个表格，{skipped} 个跳过。")


if __name__ == "__main__":
    main()
