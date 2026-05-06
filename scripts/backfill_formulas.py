"""
scripts/backfill_formulas.py
对已入库但尚无 HAS_FORMULA 关系的文档补全公式节点。

用法：
    python scripts/backfill_formulas.py --dry-run   # 只统计，不写入
    python scripts/backfill_formulas.py              # 实际写入
"""
from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_docs_without_formulas(driver) -> list[str]:
    """返回没有任何 HAS_FORMULA 关系的文档 doc_id 列表。"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            WHERE NOT (d)-[:HAS_SECTION]->(:Section)-[:HAS_FORMULA]->(:Formula)
              AND d.title IS NOT NULL
            RETURN d.name AS doc_id
            ORDER BY d.name
        """)
        return [r["doc_id"] for r in result]


def download_pdf(doc_id: str, tmp_dir: str) -> str | None:
    """从 MinIO 下载 PDF 到临时目录，返回本地路径。"""
    try:
        from src.core.storage import get_storage
        storage = get_storage()
        dest = os.path.join(tmp_dir, f"{doc_id}.pdf")
        storage.download_file(f"documents/{doc_id}.pdf", dest)
        return dest
    except Exception as e:
        logger.warning("下载 PDF 失败 doc=%s: %s", doc_id, e)
        return None


def main():
    parser = argparse.ArgumentParser(description="补全公式节点")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写入")
    args = parser.parse_args()

    from src.core.database import get_driver
    driver = get_driver()

    docs = get_docs_without_formulas(driver)
    logger.info("找到 %d 份文档没有公式节点", len(docs))

    if args.dry_run:
        print(f"\n[dry-run] 预计需要处理 {len(docs)} 份文档：")
        for doc_id in docs[:20]:
            print(f"  - {doc_id}")
        if len(docs) > 20:
            print(f"  ... 及另外 {len(docs) - 20} 份")
        return

    from src.services.formula_extractor import FormulaExtractor
    from src.services.graph.neo4j_writer import write_formulas

    extractor = FormulaExtractor()
    total_formulas = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        for doc_id in docs:
            pdf_path = download_pdf(doc_id, tmp_dir)
            if not pdf_path:
                continue
            try:
                formulas = extractor.extract_from_pdf(pdf_path, doc_id)
                if formulas:
                    written = write_formulas(doc_id, formulas)
                    total_formulas += written
                    logger.info("doc=%s formulas=%d written=%d", doc_id, len(formulas), written)
                else:
                    logger.info("doc=%s 无公式页面跳过", doc_id)
            except Exception as e:
                logger.error("处理失败 doc=%s: %s", doc_id, e)

    logger.info("补全完成，共写入公式节点 %d 个", total_formulas)


if __name__ == "__main__":
    main()
