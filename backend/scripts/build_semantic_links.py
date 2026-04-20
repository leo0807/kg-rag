#!/usr/bin/env python3
"""
scripts/build_semantic_links.py
离线批量构建跨文档 SIMILAR_TO 语义边。

用法：
    # 预览（不写库）
    python scripts/build_semantic_links.py --dry-run

    # 写入，相似度阈值 0.88，每节最多 5 条边
    python scripts/build_semantic_links.py --threshold 0.88 --top-k 5

    # 调用后端 API（无需直连数据库）
    python scripts/build_semantic_links.py --via-api --host http://localhost:8000
"""
import argparse
import sys
import os
import json

# ── 直连模式 ──────────────────────────────────────────────────────────────────
def run_direct(args):
    # 将 backend/src 加入路径
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from src.core.database  import init_db, get_driver
    from src.services.semantic_linker import build_semantic_links

    init_db()
    driver = get_driver()
    print(f"[直连] 开始构建语义边 threshold={args.threshold} top_k={args.top_k} dry_run={args.dry_run}")
    result = build_semantic_links(
        driver,
        threshold=args.threshold,
        top_k=args.top_k,
        dry_run=args.dry_run,
    )
    _print_result(result)


# ── API 模式 ──────────────────────────────────────────────────────────────────
def run_via_api(args):
    import requests
    url = f"{args.host}/api/graph/semantic-links"
    params = {"threshold": args.threshold, "top_k": args.top_k, "dry_run": args.dry_run}
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}

    print(f"[API] POST {url}  params={params}")
    resp = requests.post(url, params=params, headers=headers, timeout=300)
    if resp.status_code != 200:
        print(f"请求失败: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    _print_result(resp.json())


def _print_result(r: dict):
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if "pairs" in r:
        status = "（预览，未写入）" if r.get("dry_run") else "✓ 已写入 Neo4j"
        print(f"\n{status}: sections={r.get('sections','-')} pairs={r.get('pairs','-')} skipped={r.get('skipped','-')}")


def main():
    parser = argparse.ArgumentParser(description="构建跨文档语义相似边")
    parser.add_argument("--threshold", type=float, default=0.88, help="余弦相似度阈值（默认 0.88）")
    parser.add_argument("--top-k",     type=int,   default=5,    help="每节最多写几条边（默认 5）")
    parser.add_argument("--dry-run",   action="store_true",       help="仅统计，不写入数据库")
    parser.add_argument("--via-api",   action="store_true",       help="通过后端 HTTP API 触发")
    parser.add_argument("--host",      default="http://localhost:8000")
    parser.add_argument("--token",     default="",                help="JWT token（API 模式使用）")
    args = parser.parse_args()

    if args.via_api:
        run_via_api(args)
    else:
        run_direct(args)


if __name__ == "__main__":
    main()
