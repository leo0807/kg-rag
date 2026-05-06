"""
scripts/prepare_reranker_data.py
从 PostgreSQL 反馈表提取训练数据，构建 Reranker 对比学习数据集。

用法：
    python scripts/prepare_reranker_data.py --output data/reranker_train.jsonl
    python scripts/prepare_reranker_data.py --output data/reranker_train.jsonl --stats
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aviation:aviation123@localhost:5432/aviation",
).replace("+asyncpg", "")  # 脚本用同步驱动


SQL = """
SELECT
    f.question,
    f.sources,
    f.retrieval_score
FROM query_feedback f
WHERE f.retrieval_score IS NOT NULL
ORDER BY f.created_at DESC
LIMIT 10000
"""


def load_rows(db_url: str) -> list[dict]:
    import psycopg2
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(SQL)
    cols = [c.name for c in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    conn.close()
    return rows


def build_pairs(rows: list[dict]) -> list[dict]:
    """
    同一问题：retrieval_score>=4 的来源为正例，<=2 的为负例。
    构建所有正负例交叉对 (pos, neg)。
    """
    by_question: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"pos": [], "neg": []})

    for row in rows:
        q = (row["question"] or "").strip()
        if not q:
            continue
        score = int(row["retrieval_score"] or 0)
        try:
            sources = json.loads(row["sources"] or "[]")
        except Exception:
            continue

        for src in sources:
            chunk_content = (
                f"{src.get('doc_id','')}"
                f" §{src.get('number','')}"
                f" {src.get('title','')}"
                f"\n{src.get('content','')}"
            ).strip()
            if not chunk_content:
                continue
            if score >= 4:
                by_question[q]["pos"].append(chunk_content)
            elif score <= 2:
                by_question[q]["neg"].append(chunk_content)

    pairs: list[dict] = []
    for q, buckets in by_question.items():
        for pos in buckets["pos"]:
            # 正例单独记录
            pairs.append({"query": q, "pos": pos})
            # 正负对记录
            for neg in buckets["neg"]:
                pairs.append({"query": q, "pos": pos, "neg": neg})

    return pairs


def main():
    parser = argparse.ArgumentParser(description="准备 Reranker 微调数据")
    parser.add_argument("--output", default="data/reranker_train.jsonl", help="输出文件路径")
    parser.add_argument("--db-url", default=DB_URL, help="PostgreSQL 连接 URL")
    parser.add_argument("--stats", action="store_true", help="只打印统计，不写文件")
    args = parser.parse_args()

    logger.info("连接数据库…")
    try:
        rows = load_rows(args.db_url)
    except Exception as e:
        logger.error("数据库连接失败: %s", e)
        sys.exit(1)

    logger.info("获取反馈记录 %d 条", len(rows))
    pairs = build_pairs(rows)

    pos_only = [p for p in pairs if "neg" not in p]
    pos_neg  = [p for p in pairs if "neg" in p]
    logger.info("正例 %d 条，正负对 %d 条，合计 %d 条", len(pos_only), len(pos_neg), len(pairs))

    if args.stats:
        print(f"正例（无负例）: {len(pos_only)}")
        print(f"正负对:         {len(pos_neg)}")
        print(f"合计:           {len(pairs)}")
        return

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    logger.info("已写入 %s", args.output)


if __name__ == "__main__":
    main()
