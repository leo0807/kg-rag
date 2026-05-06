"""
scripts/eval_reranker.py
对比微调前后 Reranker 的 MRR@5 指标。

用法：
    python scripts/eval_reranker.py \
        --data data/reranker_train.jsonl \
        --baseline models/bge-reranker-v2-m3 \
        --finetuned models/reranker-cps-finetuned
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_eval_data(data_path: str, test_ratio: float = 0.2, seed: int = 42):
    """从 JSONL 中取末尾 test_ratio 作为测试集，构建 (query, pos, [neg…]) 结构。"""
    raw: list[dict] = []
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw.append(json.loads(line))

    random.seed(seed)
    random.shuffle(raw)
    split = max(1, int(len(raw) * test_ratio))
    test_raw = raw[:split]

    # 聚合成 (query, pos, neg_list)
    by_q: dict[str, dict[str, Any]] = {}
    for d in test_raw:
        q = d["query"]
        if q not in by_q:
            by_q[q] = {"pos": d["pos"], "candidates": [d["pos"]]}
        if d.get("neg"):
            by_q[q]["candidates"].append(d["neg"])

    return list(by_q.values())


def mrr_at_k(model, samples: list[dict], k: int = 5) -> float:
    """计算 MRR@k：正例在重排后的平均倒数排名。"""
    total_rr = 0.0
    for item in samples:
        query = item["query"]
        pos = item["pos"]
        candidates = list(set(item["candidates"]))
        if len(candidates) < 2:
            continue

        # 用模型打分
        pairs = [(query, c) for c in candidates]
        scores = model.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

        for rank, (text, _) in enumerate(ranked[:k], start=1):
            if text == pos:
                total_rr += 1.0 / rank
                break

    return total_rr / max(len(samples), 1)


def main():
    parser = argparse.ArgumentParser(description="评估 Reranker MRR@5")
    parser.add_argument("--data",      default="data/reranker_train.jsonl")
    parser.add_argument("--baseline",  default="models/bge-reranker-v2-m3")
    parser.add_argument("--finetuned", default="models/reranker-cps-finetuned")
    parser.add_argument("--k",         type=int, default=5)
    args = parser.parse_args()

    from sentence_transformers import CrossEncoder

    samples = load_eval_data(args.data)
    logger.info("测试样本数: %d", len(samples))
    if not samples:
        logger.error("无测试数据，退出")
        return

    logger.info("加载基线模型: %s", args.baseline)
    baseline_model = CrossEncoder(args.baseline, num_labels=1)
    baseline_mrr = mrr_at_k(baseline_model, samples, k=args.k)

    logger.info("加载微调模型: %s", args.finetuned)
    finetuned_model = CrossEncoder(args.finetuned, num_labels=1)
    finetuned_mrr = mrr_at_k(finetuned_model, samples, k=args.k)

    delta = finetuned_mrr - baseline_mrr
    print("\n========== Reranker 评估报告 ==========")
    print(f"测试集大小  : {len(samples)} 条")
    print(f"MRR@{args.k} 基线  : {baseline_mrr:.4f}")
    print(f"MRR@{args.k} 微调后: {finetuned_mrr:.4f}")
    print(f"提升        : {delta:+.4f} ({delta/max(baseline_mrr,1e-9)*100:+.1f}%)")
    print("=======================================\n")


if __name__ == "__main__":
    main()
