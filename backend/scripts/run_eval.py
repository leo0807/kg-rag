#!/usr/bin/env python3
"""
Standalone retrieval accuracy evaluation script.

Usage:
    python scripts/run_eval.py [--base-url URL] [--username USER] [--password PASS]
                               [--top-k N] [--strategy STRATEGY]

Defaults:
    base_url  = http://localhost:8000
    username  = first admin account (set via env EVAL_USERNAME / EVAL_PASSWORD)
    top_k     = 10
    strategy  = parallel
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("pip install requests  — requests is required")

EVAL_JSONL = Path(__file__).parent.parent / "eval" / "retrieval_cases.jsonl"
RESULTS_DIR = Path(__file__).parent.parent / "eval"


# ── helpers ───────────────────────────────────────────────────────────────────

def login(base_url: str, username: str, password: str) -> str:
    resp = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=15,
    )
    if resp.status_code != 200:
        sys.exit(f"Login failed {resp.status_code}: {resp.text[:300]}")
    token = resp.json().get("access_token")
    if not token:
        sys.exit(f"No access_token in response: {resp.text[:300]}")
    return token


def submit_harness(base_url: str, token: str, jsonl_path: Path, strategy: str, top_k: int) -> str:
    with jsonl_path.open("rb") as fh:
        resp = requests.post(
            f"{base_url}/api/admin/eval/retrieval",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (jsonl_path.name, fh, "application/jsonl")},
            data={"strategy": strategy, "top_k": str(top_k)},
            timeout=30,
        )
    if resp.status_code not in (200, 201):
        sys.exit(f"Submit failed {resp.status_code}: {resp.text[:300]}")
    task_id = resp.json().get("task_id")
    if not task_id:
        sys.exit(f"No task_id in response: {resp.text[:300]}")
    return task_id


def poll_until_done(base_url: str, token: str, task_id: str, interval: float = 2.0) -> dict:
    url = f"{base_url}/api/admin/eval/retrieval/{task_id}"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  Polling task {task_id}…")
    while True:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            sys.exit(f"Poll failed {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        status = data.get("status", "")
        completed = data.get("completed", 0)
        total = data.get("total", "?")
        current_q = data.get("current_question", "")[:50]
        print(f"  [{status}] {completed}/{total}  {current_q}", end="\r", flush=True)
        if status == "completed":
            print()
            return data
        if status == "failed":
            print()
            sys.exit(f"Task failed: {data.get('error', 'unknown error')}")
        time.sleep(interval)


# ── display ───────────────────────────────────────────────────────────────────

def print_results(task: dict) -> None:
    results = task.get("results", [])
    summary = task.get("summary", {})

    col_w = [4, 46, 10, 6, 6, 6, 6]
    header = f"{'#':>4}  {'Question':<46}  {'Strategy':<10}  {'Hit':>5}  {'Recall':>6}  {'MRR':>5}  {'NDCG':>5}"
    sep = "─" * len(header)
    print()
    print(sep)
    print(header)
    print(sep)
    for r in results:
        hit = "✓" if r.get("matched") else "✗"
        print(
            f"{r.get('row_no', ''):>4}  "
            f"{r.get('question', '')[:46]:<46}  "
            f"{r.get('strategy', ''):<10}  "
            f"{hit:>5}  "
            f"{float(r.get('recall', 0)):>6.3f}  "
            f"{float(r.get('reciprocal_rank', 0)):>5.3f}  "
            f"{float(r.get('ndcg', 0)):>5.3f}"
        )
    print(sep)
    print()
    print("── Summary ─────────────────────────────────────────────")
    print(f"  Total questions  : {summary.get('total', 0)}")
    print(f"  Hit count        : {summary.get('matched', 0)} / {summary.get('total', 0)}")
    print(f"  Hit Rate         : {summary.get('hit_rate', 0):.1%}")
    print(f"  Avg Recall@K     : {summary.get('avg_recall', 0):.4f}")
    print(f"  MRR              : {summary.get('mrr', 0):.4f}")
    print(f"  Avg NDCG@K       : {summary.get('avg_ndcg', 0):.4f}")
    print("─────────────────────────────────────────────────────────")
    print()


def save_results(task: dict, top_k: int, strategy: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"retrieval_{ts}_top{top_k}_{strategy}.json"
    out.write_text(json.dumps(task, ensure_ascii=False, indent=2))
    return out


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval accuracy evaluation")
    parser.add_argument("--base-url",  default=os.getenv("EVAL_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--username",  default=os.getenv("EVAL_USERNAME", ""))
    parser.add_argument("--password",  default=os.getenv("EVAL_PASSWORD", ""))
    parser.add_argument("--top-k",     type=int, default=10)
    parser.add_argument("--strategy",  default="parallel",
                        choices=["parallel", "sequential", "graph_augmented", "gnn"])
    args = parser.parse_args()

    if not args.username or not args.password:
        sys.exit(
            "Set EVAL_USERNAME and EVAL_PASSWORD env vars, "
            "or pass --username / --password"
        )

    if not EVAL_JSONL.exists():
        sys.exit(f"Test set not found: {EVAL_JSONL}")

    cases = [ln for ln in EVAL_JSONL.read_text().splitlines() if ln.strip()]
    print(f"Test set: {EVAL_JSONL.name}  ({len(cases)} cases)")
    print(f"Config  : top_k={args.top_k}  strategy={args.strategy}  url={args.base_url}")
    print()

    print("1. Authenticating…")
    token = login(args.base_url, args.username, args.password)
    print("   OK")

    print("2. Submitting retrieval harness…")
    task_id = submit_harness(args.base_url, token, EVAL_JSONL, args.strategy, args.top_k)
    print(f"   task_id = {task_id}")

    print("3. Waiting for completion…")
    task = poll_until_done(args.base_url, token, task_id)

    print_results(task)

    out = save_results(task, args.top_k, args.strategy)
    print(f"Results saved → {out}")


if __name__ == "__main__":
    main()
