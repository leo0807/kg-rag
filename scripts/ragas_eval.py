"""
RAGAS 评估脚本 — 从 query_feedback 表中提取正面反馈问答，计算四项指标。

兼容 RAGAS 0.1.x 和 0.2.x。

依赖安装：
    pip install ragas datasets psycopg2-binary

运行：
    python scripts/ragas_eval.py
"""
import json
import os
import sys

import psycopg2

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aviation:aviation123@localhost:5432/aviation",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LIMIT = int(os.getenv("RAGAS_LIMIT", "30"))

THRESHOLDS = {
    "faithfulness":        ("Faithfulness      (目标 >0.85)", 0.85),
    "answer_relevancy":    ("Answer Relevancy  (目标 >0.80)", 0.80),
    "context_recall":      ("Context Recall    (目标 >0.75)", 0.75),
    "context_precision":   ("Context Precision (目标 >0.70)", 0.70),
}


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
    for row in rows:
        question, answer, sources_raw = row[0], row[1], row[2]
        try:
            sources = json.loads(sources_raw) if sources_raw else []
        except json.JSONDecodeError:
            sources = []

        contexts = [s.get("content", "") for s in sources if s.get("content")]
        if not contexts:
            contexts = [""]

        pairs.append({
            "question":     question,
            "answer":       answer,
            "contexts":     contexts,
            "ground_truth": answer,
        })

    return pairs


def _ragas_version() -> tuple[int, ...]:
    try:
        import ragas
        return tuple(int(x) for x in ragas.__version__.split(".")[:2])
    except Exception:
        return (0, 0)


def run_evaluate(pairs: list[dict]) -> dict[str, float | None]:
    """Run RAGAS evaluate, handling both 0.1.x and 0.2.x APIs."""
    ver = _ragas_version()
    print(f"检测到 RAGAS 版本前缀: {ver}")

    if ver >= (0, 2):
        return _evaluate_v2(pairs)
    else:
        return _evaluate_v1(pairs)


def _evaluate_v1(pairs: list[dict]) -> dict[str, float | None]:
    from datasets import Dataset
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
    return {
        "faithfulness":      result["faithfulness"],
        "answer_relevancy":  result["answer_relevancy"],
        "context_recall":    result["context_recall"],
        "context_precision": result["context_precision"],
    }


def _evaluate_v2(pairs: list[dict]) -> dict[str, float | None]:
    from ragas import evaluate
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
    from ragas.metrics import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )

    samples = [
        SingleTurnSample(
            user_input=p["question"],
            response=p["answer"],
            retrieved_contexts=p["contexts"],
            reference=p["ground_truth"],
        )
        for p in pairs
    ]
    dataset = EvaluationDataset(samples=samples)
    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()],
    )
    df = result.to_pandas()
    return {
        key: float(df[key].mean()) if key in df.columns else None
        for key in ("faithfulness", "answer_relevancy", "context_recall", "context_precision")
    }


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

    scores = run_evaluate(pairs)

    print("=" * 50)
    print("RAGAS 评估结果")
    print("=" * 50)
    for key, (label, threshold) in THRESHOLDS.items():
        score = scores.get(key)
        if score is None:
            print(f"  —  {label}: N/A")
        else:
            status = "✅" if score >= threshold else "⚠️"
            print(f"  {status} {label}: {score:.4f}")

    print("\n原始分数:", scores)


if __name__ == "__main__":
    main()
