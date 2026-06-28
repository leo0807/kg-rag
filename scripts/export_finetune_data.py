#!/usr/bin/env python3
"""
Export fine-tuning data from user feedback.

Extracts high-quality QA pairs (rating=1/thumbs-up) from query_feedback
and exports in SFT format (Alpaca / ShareGPT) for LoRA fine-tuning.

Usage:
    python scripts/export_finetune_data.py \
        --db-url postgresql://aviation:password@localhost:5432/aviation \
        --output-dir scripts/finetune_data \
        --format alpaca \
        --min-rating 1

Output formats:
    alpaca: [{"instruction": ..., "input": ..., "output": ...}]
    sharegpt: [{"conversations": [{"from": "human", "value": ...}, {"from": "gpt", "value": ...}]}]
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def export_feedback_pairs(db_url: str, min_rating: int = 1,
                          limit: int = 10000) -> list[dict]:
    """Query database for high-quality feedback pairs."""
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT f.question, f.answer, f.context, f.rating, f.created_at
            FROM query_feedback f
            WHERE f.rating >= %s
              AND f.question IS NOT NULL
              AND f.answer IS NOT NULL
              AND length(f.answer) > 50
            ORDER BY f.created_at DESC
            LIMIT %s
            """,
            (min_rating, limit),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "question": r[0],
                "answer": r[1],
                "context": r[2] or "",
                "rating": r[3],
                "created_at": str(r[4]),
            }
            for r in rows
        ]
    except ImportError:
        print("psycopg2 not installed. Run: pip install psycopg2-binary")
        return []
    except Exception as exc:
        print(f"Database error: {exc}")
        return []


def to_alpaca(pairs: list[dict]) -> list[dict]:
    """Convert to Alpaca SFT format."""
    return [
        {
            "instruction": "你是航空工艺知识库助手，请根据以下上下文准确回答问题。",
            "input": f"上下文:\n{p['context'][:2000]}\n\n问题: {p['question']}" if p["context"] else p["question"],
            "output": p["answer"],
        }
        for p in pairs
    ]


def to_sharegpt(pairs: list[dict]) -> list[dict]:
    """Convert to ShareGPT format."""
    results = []
    for p in pairs:
        convs = []
        if p["context"]:
            convs.append({
                "from": "system",
                "value": f"你是航空工艺知识库助手。以下是相关上下文:\n{p['context'][:2000]}",
            })
        convs.extend([
            {"from": "human", "value": p["question"]},
            {"from": "gpt", "value": p["answer"]},
        ])
        results.append({"conversations": convs})
    return results


def build_raft_dataset(pairs: list[dict],
                        noise_ratio: int = 3) -> list[dict]:
    """
    Build RAFT dataset: 1 relevant + N distractor contexts per sample.
    Trains the model to identify and use only the relevant context.
    """
    import random
    all_contexts = [p["context"] for p in pairs if p.get("context")]
    raft_samples = []
    for p in pairs:
        if not p.get("context"):
            continue
        distractors = random.sample(
            [c for c in all_contexts if c != p["context"]],
            min(noise_ratio, len(all_contexts) - 1),
        )
        all_ctxs = [p["context"]] + distractors
        random.shuffle(all_ctxs)
        context_str = "\n\n---\n\n".join(
            f"文档片段 {i+1}:\n{c[:500]}" for i, c in enumerate(all_ctxs)
        )
        raft_samples.append({
            "instruction": (
                "以下是若干文档片段，其中只有部分与问题相关。"
                "请仅基于相关片段回答问题，忽略不相关内容，"
                "并在答案中用 <citation> 标注所用片段编号。"
            ),
            "input": f"{context_str}\n\n问题: {p['question']}",
            "output": p["answer"],
        })
    return raft_samples


def main() -> None:
    parser = argparse.ArgumentParser(description="Export fine-tuning data")
    parser.add_argument("--db-url",
                        default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--output-dir", default="scripts/finetune_data")
    parser.add_argument("--format", default="alpaca",
                        choices=["alpaca", "sharegpt", "raft"])
    parser.add_argument("--min-rating", type=int, default=1)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--raft-noise", type=int, default=3)
    args = parser.parse_args()

    print(f"Exporting fine-tuning data (format={args.format}, min_rating={args.min_rating})")
    pairs = export_feedback_pairs(args.db_url, args.min_rating, args.limit)
    print(f"Found {len(pairs)} high-quality QA pairs")

    if not pairs:
        print("No data found. Exiting.")
        return

    if args.format == "alpaca":
        data = to_alpaca(pairs)
    elif args.format == "sharegpt":
        data = to_sharegpt(pairs)
    elif args.format == "raft":
        data = build_raft_dataset(pairs, args.raft_noise)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"finetune_{args.format}_{ts}.json"

    with open(out_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Exported {len(data)} samples to: {out_file}")
    print(f"  Average answer length: {sum(len(d.get('output', '')) for d in data) // len(data)} chars")


if __name__ == "__main__":
    main()
