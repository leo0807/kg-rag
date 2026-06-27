#!/usr/bin/env python3
"""
A/B strategy comparison for retrieval evaluation.

Compares two retrieval strategies over the same QA benchmark set and
applies a Wilcoxon signed-rank test to determine statistical significance.

Usage:
    python scripts/eval/ab_test.py \
        --strategy-a parallel \
        --strategy-b graph_augmented \
        --endpoint http://localhost:8000 \
        --qa-file scripts/eval/benchmark_questions.json \
        --output-dir scripts/eval/results
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx


def load_qa_pairs(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("questions", data.get("qa_pairs", []))


def query_backend(
    endpoint: str,
    question: str,
    strategy: str,
    api_key: str,
) -> tuple[str, list[str]]:
    headers = {"X-API-Key": api_key} if api_key else {}
    r = httpx.post(
        f"{endpoint}/api/query",
        json={"question": question, "strategy": strategy, "top_k": 5},
        headers=headers,
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    answer = data.get("answer", "")
    contexts = [s.get("content", s.get("text", "")) for s in data.get("sources", [])]
    return answer, contexts


def context_recall(contexts: list[str], ground_truth: str, window: int = 100) -> float:
    """Simple overlap-based recall: fraction of ground truth words found in contexts."""
    gt_words = set(ground_truth.lower().split())
    if not gt_words:
        return 0.0
    ctx_text = " ".join(contexts).lower()
    found = sum(1 for w in gt_words if w in ctx_text)
    return found / len(gt_words)


def mrr(contexts: list[str], ground_truth: str) -> float:
    """Mean Reciprocal Rank: 1/rank of first context containing ground truth."""
    snippet = ground_truth[:80].lower()
    for i, ctx in enumerate(contexts):
        if snippet in ctx.lower():
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(contexts: list[str], ground_truth: str, k: int = 3) -> float:
    """Recall@K: 1 if ground truth appears in top-K contexts, else 0."""
    snippet = ground_truth[:80].lower()
    return float(any(snippet in c.lower() for c in contexts[:k]))


def run_strategy(
    qa_pairs: list[dict],
    strategy: str,
    endpoint: str,
    api_key: str,
) -> list[dict]:
    results = []
    for i, qa in enumerate(qa_pairs):
        question = qa.get("question", qa.get("q", ""))
        ground_truth = qa.get("answer", qa.get("a", qa.get("ground_truth", "")))
        try:
            answer, contexts = query_backend(endpoint, question, strategy, api_key)
        except Exception as exc:
            print(f"  [{strategy}] [{i+1}] SKIP: {exc}", file=sys.stderr)
            continue
        results.append({
            "question":       question,
            "answer":         answer,
            "contexts":       contexts,
            "ground_truth":   ground_truth,
            "recall":         context_recall(contexts, ground_truth),
            "mrr":            mrr(contexts, ground_truth),
            "recall_at_3":    recall_at_k(contexts, ground_truth, 3),
        })
        print(f"  [{strategy}] [{i+1}/{len(qa_pairs)}] recall={results[-1]['recall']:.2f}")
    return results


def wilcoxon(x: list[float], y: list[float]) -> tuple[float, str]:
    """
    Wilcoxon signed-rank test (manual implementation to avoid scipy dependency).
    Returns (W-statistic, 'significant'|'not significant') at alpha=0.05.
    Only approximate for n > 10 using normal approximation.
    """
    diffs = [xi - yi for xi, yi in zip(x, y) if xi != yi]
    n = len(diffs)
    if n == 0:
        return 0.0, "no difference"

    abs_diffs = sorted(enumerate(abs(d) for d in diffs), key=lambda t: t[1])
    ranks = {orig_i: rank + 1 for rank, (orig_i, _) in enumerate(abs_diffs)}

    w_plus  = sum(ranks[i] for i, d in enumerate(diffs) if d > 0)
    w_minus = sum(ranks[i] for i, d in enumerate(diffs) if d < 0)
    w_stat  = min(w_plus, w_minus)

    # Normal approximation for n >= 10
    if n >= 10:
        mean_w = n * (n + 1) / 4.0
        std_w  = ((n * (n + 1) * (2 * n + 1)) / 24.0) ** 0.5
        z = (w_stat - mean_w) / std_w if std_w > 0 else 0
        # Two-tailed p < 0.05 corresponds to |z| > 1.96
        significant = abs(z) > 1.96
        return w_stat, "significant (p<0.05)" if significant else "not significant"

    # For small n, use critical value table (alpha=0.05, two-tailed)
    critical = {5: 0, 6: 2, 7: 3, 8: 5, 9: 8}
    threshold = critical.get(n, 0)
    significant = w_stat <= threshold
    return w_stat, "significant (p<0.05)" if significant else "not significant"


def compare(
    results_a: list[dict],
    results_b: list[dict],
    strategy_a: str,
    strategy_b: str,
) -> dict:
    n = min(len(results_a), len(results_b))
    recall_a = [r["recall"] for r in results_a[:n]]
    recall_b = [r["recall"] for r in results_b[:n]]
    mrr_a    = [r["mrr"]    for r in results_a[:n]]
    mrr_b    = [r["mrr"]    for r in results_b[:n]]
    r3_a     = [r["recall_at_3"] for r in results_a[:n]]
    r3_b     = [r["recall_at_3"] for r in results_b[:n]]

    avg = lambda lst: sum(lst) / len(lst) if lst else 0.0

    w_recall, sig_recall = wilcoxon(recall_a, recall_b)
    w_mrr,    sig_mrr    = wilcoxon(mrr_a,    mrr_b)

    winner = strategy_a if avg(recall_a) >= avg(recall_b) else strategy_b

    return {
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "n_pairs":    n,
        "evaluated_at": datetime.utcnow().isoformat(),
        "metrics": {
            "recall": {
                "a": round(avg(recall_a), 4),
                "b": round(avg(recall_b), 4),
                "wilcoxon_W":   w_recall,
                "significance": sig_recall,
            },
            "mrr": {
                "a": round(avg(mrr_a), 4),
                "b": round(avg(mrr_b), 4),
                "wilcoxon_W":   w_mrr,
                "significance": sig_mrr,
            },
            "recall_at_3": {
                "a": round(avg(r3_a), 4),
                "b": round(avg(r3_b), 4),
            },
        },
        "recommendation": winner,
        "per_question": [
            {
                "question": results_a[i]["question"],
                f"recall_{strategy_a}": recall_a[i],
                f"recall_{strategy_b}": recall_b[i],
                f"mrr_{strategy_a}": mrr_a[i],
                f"mrr_{strategy_b}": mrr_b[i],
            }
            for i in range(n)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B retrieval strategy comparison")
    parser.add_argument("--strategy-a", default="parallel",
                        choices=["parallel", "graph_augmented", "sequential", "multi_hop"])
    parser.add_argument("--strategy-b", default="graph_augmented",
                        choices=["parallel", "graph_augmented", "sequential", "multi_hop"])
    parser.add_argument("--endpoint", default="http://localhost:8000")
    parser.add_argument("--qa-file", default="scripts/eval/benchmark_questions.json")
    parser.add_argument("--output-dir", default="scripts/eval/results")
    parser.add_argument("--api-key", default=os.getenv("BACKEND_API_KEY", ""))
    args = parser.parse_args()

    qa_pairs = load_qa_pairs(args.qa_file)
    print(f"Loaded {len(qa_pairs)} QA pairs\n")

    print(f"Running strategy A: {args.strategy_a}")
    results_a = run_strategy(qa_pairs, args.strategy_a, args.endpoint, args.api_key)

    print(f"\nRunning strategy B: {args.strategy_b}")
    results_b = run_strategy(qa_pairs, args.strategy_b, args.endpoint, args.api_key)

    report = compare(results_a, results_b, args.strategy_a, args.strategy_b)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"ab_{args.strategy_a}_vs_{args.strategy_b}_{ts}.json"
    with open(out_file, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    m = report["metrics"]
    print(f"\n{'='*55}")
    print(f"A/B Test: {args.strategy_a} vs {args.strategy_b}  (n={report['n_pairs']})")
    print(f"{'='*55}")
    print(f"  Recall      A={m['recall']['a']:.3f}  B={m['recall']['b']:.3f}  → {m['recall']['significance']}")
    print(f"  MRR         A={m['mrr']['a']:.3f}  B={m['mrr']['b']:.3f}  → {m['mrr']['significance']}")
    print(f"  Recall@3    A={m['recall_at_3']['a']:.3f}  B={m['recall_at_3']['b']:.3f}")
    print(f"\n  ★ Recommendation: {report['recommendation']}")
    print(f"\nReport saved to: {out_file}")


if __name__ == "__main__":
    main()
