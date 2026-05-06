"""
scripts/finetune_reranker.py
基于对比学习数据微调 BGE-Reranker-v2-m3。

用法：
    python scripts/finetune_reranker.py \
        --data data/reranker_train.jsonl \
        --base-model models/bge-reranker-v2-m3 \
        --output models/reranker-cps-finetuned \
        --epochs 3 \
        --batch-size 16
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_samples(data_path: str):
    from sentence_transformers import InputExample
    samples = []
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if not d.get("query") or not d.get("pos"):
                continue
            samples.append(InputExample(texts=[d["query"], d["pos"]], label=1.0))
            if d.get("neg"):
                samples.append(InputExample(texts=[d["query"], d["neg"]], label=0.0))
    return samples


def finetune(
    data_path: str,
    base_model: str,
    output_path: str,
    epochs: int = 3,
    batch_size: int = 16,
    warmup_steps: int = 100,
):
    from sentence_transformers import CrossEncoder
    from torch.utils.data import DataLoader

    logger.info("加载基础模型: %s", base_model)
    model = CrossEncoder(base_model, num_labels=1)

    samples = load_samples(data_path)
    if not samples:
        logger.error("训练数据为空，请先运行 prepare_reranker_data.py")
        sys.exit(1)

    logger.info("训练样本数: %d", len(samples))
    train_loader = DataLoader(samples, shuffle=True, batch_size=batch_size)

    model.fit(
        train_dataloader=train_loader,
        epochs=epochs,
        warmup_steps=warmup_steps,
        output_path=output_path,
        show_progress_bar=True,
    )
    logger.info("微调完成，模型保存到 %s", output_path)
    print(f"\n切换到微调模型：在 .env 中设置 RERANKER_MODEL={output_path}")


def main():
    parser = argparse.ArgumentParser(description="微调 BGE-Reranker")
    parser.add_argument("--data",       default="data/reranker_train.jsonl")
    parser.add_argument("--base-model", default="models/bge-reranker-v2-m3")
    parser.add_argument("--output",     default="models/reranker-cps-finetuned")
    parser.add_argument("--epochs",     type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--warmup",     type=int, default=100)
    args = parser.parse_args()

    finetune(
        data_path=args.data,
        base_model=args.base_model,
        output_path=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        warmup_steps=args.warmup,
    )


if __name__ == "__main__":
    main()
