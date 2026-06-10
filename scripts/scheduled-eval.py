#!/usr/bin/env python3
"""
scheduled-eval.py — 定时评测脚本（每周自动跑一次，对比上周结果）
通过 cron 调用：0 3 * * 0 python3 /path/to/kg-rag/scripts/scheduled-eval.py

依赖：后端服务必须运行在 http://localhost:8000
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

BASE_URL = os.getenv("KG_RAG_URL", "http://localhost:8000")
ADMIN_TOKEN = os.getenv("KG_RAG_ADMIN_TOKEN", "")
DATASET_ID = os.getenv("EVAL_DATASET_ID", "")
STRATEGIES = os.getenv("EVAL_STRATEGIES", "parallel,graph").split(",")
REPORT_DIR = Path(os.getenv("EVAL_REPORT_DIR", "/tmp/kg-rag-eval-reports"))


def _req(method: str, path: str, body: Optional[dict] = None) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {ADMIN_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} on {method} {path}: {e.read()[:200]}")
        return {}


def _wait_run(run_id: str, max_wait: int = 3600) -> dict:
    for _ in range(max_wait // 10):
        info = _req("GET", f"/api/admin/eval/runs/{run_id}")
        status = info.get("status", "")
        prog = info.get("progress", 0)
        print(f"  进度: {prog}%  状态: {status}", end="\r")
        if status in ("completed", "cancelled", "failed"):
            print()
            return info
        time.sleep(10)
    return {}


def main() -> int:
    if not ADMIN_TOKEN:
        print("❌ 需要设置 KG_RAG_ADMIN_TOKEN 环境变量")
        return 1
    if not DATASET_ID:
        print("❌ 需要设置 EVAL_DATASET_ID 环境变量")
        return 1

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_ids = []

    print(f"=== 定时评测 开始 | 数据集: {DATASET_ID} ===")
    for strategy in STRATEGIES:
        print(f"\n[{strategy}] 启动评测...")
        resp = _req("POST", "/api/admin/eval/runs", {
            "dataset_id": DATASET_ID,
            "strategy": strategy,
            "run_name": f"scheduled-{strategy}-{time.strftime('%Y%m%d')}",
            "tags": ["scheduled", f"strategy:{strategy}"],
        })
        run_id = resp.get("run_id")
        if not run_id:
            print(f"  ❌ 启动失败: {resp}")
            continue
        print(f"  Run ID: {run_id}")
        info = _wait_run(run_id)
        acc = info.get("accuracy") or 0
        print(f"  ✓ 完成 | 准确率: {acc:.1%}")
        run_ids.append(run_id)

        # Trigger error analysis
        _req("POST", f"/api/admin/eval/runs/{run_id}/analyze")

    if not run_ids:
        print("❌ 没有成功完成的评测")
        return 1

    # Generate comparison report
    print(f"\n生成报告（{len(run_ids)} 个 runs）...")
    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"eval_report_{ts}.txt"

    best_run = run_ids[0]
    report_resp = _req("POST", f"/api/admin/eval/runs/{best_run}/generate-report?fmt=txt")
    if report_resp:
        print(f"✓ 报告已生成")

    # Save run IDs
    meta_path = REPORT_DIR / f"run_ids_{ts}.json"
    meta_path.write_text(json.dumps({"run_ids": run_ids, "timestamp": ts}))
    print(f"✓ Run IDs 已保存: {meta_path}")

    # Send alert if configured
    webhook = os.getenv("WECOM_WEBHOOK") or os.getenv("DINGTALK_WEBHOOK")
    if webhook:
        summary = ", ".join(f"{s}:run{i}" for i, s in enumerate(STRATEGIES[:len(run_ids)]))
        msg = f"📊 KG-RAG 定时评测完成\n{summary}\n详情: {BASE_URL}/admin/eval"
        try:
            req = urllib.request.Request(webhook, method="POST")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req,
                data=json.dumps({"msgtype": "text", "text": {"content": msg}}).encode(),
                timeout=10)
        except Exception as e:
            print(f"⚠️  告警推送失败: {e}")

    print("\n✅ 定时评测完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
