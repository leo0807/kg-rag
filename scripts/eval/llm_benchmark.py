#!/usr/bin/env python3
"""LLM benchmark: evaluate query API against sample questions with BLEU + ROUGE-L."""

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# Minimal ngram-based BLEU (no external dep needed beyond standard library)
# ---------------------------------------------------------------------------

def _ngrams(tokens: list[str], n: int) -> Counter:
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


def bleu_score(hypothesis: str, reference: str, max_n: int = 4) -> float:
    hyp_tokens = hypothesis.lower().split()
    ref_tokens = reference.lower().split()
    if not hyp_tokens:
        return 0.0

    log_score = 0.0
    for n in range(1, max_n + 1):
        hyp_ngrams = _ngrams(hyp_tokens, n)
        ref_ngrams = _ngrams(ref_tokens, n)
        clipped = sum(min(c, ref_ngrams[g]) for g, c in hyp_ngrams.items())
        total = max(sum(hyp_ngrams.values()), 1)
        precision = clipped / total
        if precision == 0:
            return 0.0
        log_score += math.log(precision) / max_n

    # Brevity penalty
    bp = min(1.0, math.exp(1 - len(ref_tokens) / max(len(hyp_tokens), 1)))
    return bp * math.exp(log_score)


# ---------------------------------------------------------------------------
# Minimal ROUGE-L (LCS-based)
# ---------------------------------------------------------------------------

def _lcs_length(a: list[str], b: list[str]) -> int:
    m, n = len(a), len(b)
    dp = [0] * (n + 1)
    for i in range(1, m + 1):
        prev = 0
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev + 1 if a[i - 1] == b[j - 1] else max(dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def rouge_l(hypothesis: str, reference: str) -> float:
    hyp = hypothesis.lower().split()
    ref = reference.lower().split()
    if not hyp or not ref:
        return 0.0
    lcs = _lcs_length(hyp, ref)
    precision = lcs / len(hyp)
    recall = lcs / len(ref)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def query_backend(endpoint: str, api_key: str, question: str, timeout: int = 30) -> str:
    url = f"{endpoint.rstrip('/')}/api/v1/query"
    payload = {"question": question, "mode": "hybrid", "top_k": 5}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        # Support both {"answer": "..."} and {"data": {"answer": "..."}}
        return data.get("answer") or data.get("data", {}).get("answer", "")
    except requests.RequestException as exc:
        return f"[ERROR: {exc}]"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_benchmark(args: argparse.Namespace) -> int:
    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"Questions file not found: {questions_path}", file=sys.stderr)
        return 1

    with open(questions_path, encoding="utf-8") as f:
        questions = json.load(f)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total_bleu = total_rouge = 0.0

    print(f"{'ID':<6} {'Diff':<8} {'BLEU':>6} {'ROUGE-L':>8}  Question")
    print("-" * 70)

    for q in questions:
        answer = query_backend(args.endpoint, args.api_key, q["question"])
        expected = q.get("expected_answer", "")
        b = bleu_score(answer, expected) if expected else 0.0
        r = rouge_l(answer, expected) if expected else 0.0
        total_bleu += b
        total_rouge += r

        print(f"{q['id']:<6} {q.get('difficulty','?'):<8} {b:>6.3f} {r:>8.3f}  {q['question'][:50]}")
        results.append({
            "id": q["id"],
            "question": q["question"],
            "difficulty": q.get("difficulty", "unknown"),
            "expected_answer": expected,
            "actual_answer": answer,
            "bleu": round(b, 4),
            "rouge_l": round(r, 4),
        })

    n = len(questions)
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "endpoint": args.endpoint,
        "total_questions": n,
        "avg_bleu": round(total_bleu / n, 4) if n else 0,
        "avg_rouge_l": round(total_rouge / n, 4) if n else 0,
        "results": results,
    }

    print("-" * 70)
    print(f"Avg BLEU: {summary['avg_bleu']:.4f}  Avg ROUGE-L: {summary['avg_rouge_l']:.4f}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"benchmark_{ts}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {out_file}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LLM benchmark for KG-RAG query API")
    p.add_argument("--endpoint", default=os.getenv("BACKEND_URL", "http://localhost:8000"),
                   help="Backend base URL (default: http://localhost:8000)")
    p.add_argument("--api-key", default=os.getenv("API_KEY", ""),
                   help="Bearer API key (or set API_KEY env var)")
    p.add_argument("--questions", default=str(Path(__file__).parent / "benchmark_questions.json"),
                   help="Path to benchmark_questions.json")
    p.add_argument("--output-dir", default=str(Path(__file__).parent / "results"),
                   help="Directory to write result JSON files")
    return p


if __name__ == "__main__":
    parser = build_parser()
    parsed = parser.parse_args()
    sys.exit(run_benchmark(parsed))
