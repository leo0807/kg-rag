"""
RAGAS 评估脚本 — 从 query_feedback 表中提取正面反馈问答，计算四项指标。

依赖安装：
    pip install ragas datasets psycopg2-binary

运行：
    python scripts/ragas_eval.py
"""
import json
import os
import sys

import psycopg2
from datasets import Dataset

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aviation:aviation123@localhost:5432/aviation",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LIMIT = int(os.getenv("RAGAS_LIMIT", "30"))


def fetch_qa_pairs() -> list[dict]:
    conn = psycopg2.connect(DB_URL)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT question, answer, sources
            FROM query_feedback
            WHERE rating = 1
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (LIMIT,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    pairs = []
    for question, answer, sources_raw in rows:
        try:
            sources = json.loads(sources_raw) if sources_raw else []
        except json.JSONDecodeError:
            sources = []

        contexts = [s.get("content", "") for s in sources if s.get("content")]
        if not contexts:
            contexts = [""]

        pairs.append({
            "question":  question,
            "answer":    answer,
            "contexts":  contexts,
            # ground_truth 留空（无标注答案时 context_recall 会跳过）
            "ground_truth": answer,
        })

    return pairs


def main():
    if not OPENAI_API_KEY:
        print("警告: OPENAI_API_KEY 未设置，RAGAS 将使用默认 LLM 配置。")
        print("可通过 export OPENAI_API_KEY=... 设置。\n")

    print("正在从数据库拉取正面反馈问答...")
    pairs = fetch_qa_pairs()
    if not pairs:
        print("未找到 rating=1 的反馈记录，请先收集用户反馈。")
        sys.exit(0)

    print(f"共获取 {len(pairs)} 条问答对，开始评估...\n")

    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    dataset = Dataset.from_list(pairs)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
    )

    print("=" * 50)
    print("RAGAS 评估结果")
    print("=" * 50)
    scores = {
        "Faithfulness      (目标 >0.85)": result["faithfulness"],
        "Answer Relevancy  (目标 >0.80)": result["answer_relevancy"],
        "Context Recall    (目标 >0.75)": result["context_recall"],
        "Context Precision (目标 >0.70)": result["context_precision"],
    }
    for label, score in scores.items():
        status = "✅" if score is not None and score >= float(label.split(">")[1].rstrip(")")) else "⚠️"
        print(f"  {status} {label}: {score:.4f}" if score is not None else f"  — {label}: N/A")

    print("\n原始结果对象:", result)


if __name__ == "__main__":
    main()
