#!/usr/bin/env python3
"""
scripts/export_training_data.py
从反馈数据库导出高质量问答对，用于微调 bge-reranker

用法：
    python scripts/export_training_data.py
    python scripts/export_training_data.py --format reranker --out data/reranker_train.jsonl
    python scripts/export_training_data.py --format jsonl --min-rating 1
"""
import argparse
import sys
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser(description="导出训练数据")
    parser.add_argument("--host",       default="http://localhost:8000", help="后端地址")
    parser.add_argument("--token",      default="",  help="JWT token（如需认证）")
    parser.add_argument("--format",     default="jsonl", choices=["jsonl", "reranker"],
                        help="导出格式：jsonl（原始）/ reranker（bge微调格式）")
    parser.add_argument("--min-rating", default=1, type=int,
                        help="最小评分过滤，1=仅正向，-1=全部")
    parser.add_argument("--out",        default="", help="输出文件路径（默认打印到 stdout）")
    args = parser.parse_args()

    url = f"{args.host}/api/feedback/export"
    params = {"format": args.format, "min_rating": args.min_rating}
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"请求失败: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    content = resp.text
    count = content.strip().count("\n") + 1 if content.strip() else 0

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"✓ 导出 {count} 条记录 → {out_path}")
    else:
        print(content, end="")
        print(f"\n# 共 {count} 条", file=sys.stderr)


if __name__ == "__main__":
    main()
