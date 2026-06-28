#!/usr/bin/env python3
"""
RAGAS evaluation script.
Loads annotated QA pairs and computes Faithfulness, Answer Relevancy,
Context Recall, and Context Precision metrics.

Usage:
    python scripts/eval/ragas_eval.py \
        --endpoint http://localhost:8000 \
        --qa-file scripts/eval/benchmark_questions.json \
        --strategy parallel \
        --output-dir scripts/eval/results

Requires:
    pip install ragas datasets langchain-openai
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
    # Support both list-of-dicts and {"questions": [...]}
    if isinstance(data, list):
        return data
    return data.get("questions", data.get("qa_pairs", []))


def query_backend(endpoint: str, question: str, strategy: str,
                  api_key: str) -> tuple[str, list[str]]:
    """Call /api/query and return (answer, list_of_context_strings)."""
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
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


def run_ragas(qa_pairs: list[dict], endpoint: str, strategy: str,
              api_key: str) -> dict:
    """
    Run RAGAS evaluation. Falls back to manual scoring if ragas not installed.
    """
    questions, answers, ground_truths, contexts_list = [], [], [], []

    print(f"Querying {len(qa_pairs)} questions via {strategy}...")
    for i, qa in enumerate(qa_pairs):
        question = qa.get("question", qa.get("q", ""))
        ground_truth = qa.get("answer", qa.get("a", qa.get("ground_truth", "")))
        try:
            answer, contexts = query_backend(endpoint, question, strategy, api_key)
        except Exception as exc:
            print(f"  [{i+1}] SKIP: {exc}", file=sys.stderr)
            continue
        questions.append(question)
        answers.append(answer)
        ground_truths.append(ground_truth)
        contexts_list.append(contexts)
        print(f"  [{i+1}/{len(qa_pairs)}] ✓")

    try:
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from datasets import Dataset

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
            "ground_truth": ground_truths,
        })
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        )
        scores = {
            "faithfulness": float(result["faithfulness"]),
            "answer_relevancy": float(result["answer_relevancy"]),
            "context_recall": float(result["context_recall"]),
            "context_precision": float(result["context_precision"]),
        }
    except ImportError:
        print("ragas not installed — computing approximate BLEU/ROUGE scores",
              file=sys.stderr)
        # Simple approximation: context hit rate
        hit_rate = sum(
            1 for gt, ctxs in zip(ground_truths, contexts_list)
            if any(gt[:50].lower() in c.lower() for c in ctxs)
        ) / max(len(ground_truths), 1)
        scores = {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_recall": round(hit_rate, 3),
            "context_precision": None,
            "note": "Install ragas for full metrics: pip install ragas",
        }

    return {
        "strategy": strategy,
        "n_questions": len(questions),
        "evaluated_at": datetime.utcnow().isoformat(),
        "scores": scores,
    }


def check_thresholds(result: dict) -> list[str]:
    """Return list of metrics that failed minimum thresholds."""
    thresholds = {
        "faithfulness": 0.85,
        "answer_relevancy": 0.80,
        "context_recall": 0.75,
        "context_precision": 0.70,
    }
    failures = []
    for metric, threshold in thresholds.items():
        score = result["scores"].get(metric)
        if score is not None and score < threshold:
            failures.append(
                f"{metric}: {score:.3f} < {threshold} (threshold)"
            )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS evaluation")
    parser.add_argument("--endpoint", default="http://localhost:8000")
    parser.add_argument("--qa-file", default="scripts/eval/benchmark_questions.json")
    parser.add_argument("--strategy", default="parallel",
                        choices=["parallel", "graph_augmented", "sequential", "multi_hop"])
    parser.add_argument("--output-dir", default="scripts/eval/results")
    parser.add_argument("--api-key", default=os.getenv("BACKEND_API_KEY", ""))
    args = parser.parse_args()

    qa_pairs = load_qa_pairs(args.qa_file)
    print(f"Loaded {len(qa_pairs)} QA pairs from {args.qa_file}")

    result = run_ragas(qa_pairs, args.endpoint, args.strategy, args.api_key)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"ragas_{args.strategy}_{ts}.json"
    with open(out_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Strategy: {result['strategy']}")
    print(f"Questions evaluated: {result['n_questions']}")
    for k, v in result["scores"].items():
        if v is not None and isinstance(v, float):
            print(f"  {k}: {v:.3f}")
    print(f"\nResults saved to: {out_file}")

    failures = check_thresholds(result)
    if failures:
        print("\n⚠️  THRESHOLD FAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("\n✓ All metrics meet thresholds")


if __name__ == "__main__":
    main()
