#!/usr/bin/env python3
"""
图谱链路预测脚本 — 建议每周定时运行一次。

用法:
    python scripts/run_link_prediction.py [--top-k 50]

结果写入 Redis key: graph:predictions（TTL 7天）
"""
import argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=50)
    args = parser.parse_args()

    from backend.src.core.database import get_driver  # type: ignore
    from backend.src.services.graph.link_prediction import run_and_cache_predictions

    driver = get_driver()
    results = run_and_cache_predictions(driver, top_k=args.top_k)
    print(f"链路预测完成：共 {len(results)} 条候选关系已写入 Redis")
    for r in results[:10]:
        print(f"  [{r['source_label']}] {r['source_name']}  ↔  [{r['target_label']}] {r['target_name']}  (score={r['score']})")


if __name__ == "__main__":
    main()
