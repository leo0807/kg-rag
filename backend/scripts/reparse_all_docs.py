"""
scripts/reparse_all_docs.py
全量重新解析所有文档并写回 Neo4j（断点续跑）

用法：
    cd backend/
    python scripts/reparse_all_docs.py --dry-run
    python scripts/reparse_all_docs.py --from CPS0500
    python scripts/reparse_all_docs.py --limit 10
    python scripts/reparse_all_docs.py --only-flat
    python scripts/reparse_all_docs.py
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.core.logging import setup_logging
from src.core.database import init_db, get_driver
from scripts.reparse_all_docs_helpers import neo4j_rewrite_sections, parse_doc

setup_logging()
logger = logging.getLogger(__name__)

PROGRESS_FILE = Path("/tmp/reparse_all_progress.json")


# ── 进度持久化 ──────────────────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"completed": [], "failed": {}, "started_at": datetime.now(timezone.utc).isoformat()}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 文档列表查询 ──────────────────────────────────────────────────────────────

def fetch_docs(driver, only_flat: bool = False) -> list[dict]:
    """返回所有待处理文档（跳过 invalid），每项包含 doc_id / storage_key / max_level"""
    with driver.session() as s:
        rows = list(s.run("""
            MATCH (d:Document)
            WHERE d.storage_key IS NOT NULL
              AND coalesce(d.status, '') <> 'invalid'
            OPTIONAL MATCH (d)-[:HAS_SECTION]->(sec:Section)
            WITH d, max(coalesce(sec.level, 1)) AS max_level
            RETURN d.name AS doc_id,
                   d.storage_key AS storage_key,
                   max_level
            ORDER BY d.name
        """))
    docs = [
        {
            "doc_id":      r["doc_id"],
            "storage_key": r["storage_key"],
            "max_level":   r["max_level"] or 1,
        }
        for r in rows
        if r["doc_id"] and r["storage_key"]
    ]
    if only_flat:
        docs = [d for d in docs if d["max_level"] <= 1]
    return docs


# ── 统计 ─────────────────────────────────────────────────────────────────────

def section_stats(driver) -> tuple[int, dict]:
    with driver.session() as s:
        total = s.run("MATCH (s:Section) RETURN count(s) AS n").single()["n"]
        rows  = list(s.run(
            "MATCH (s:Section) RETURN coalesce(s.level,1) AS lv, count(s) AS cnt ORDER BY lv"
        ))
    levels = {r["lv"]: r["cnt"] for r in rows}
    return total, levels


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="全量重新解析文档并写回 Neo4j")
    parser.add_argument("--dry-run",   action="store_true", help="只统计，不实际处理")
    parser.add_argument("--from",      dest="from_doc",  default="", help="从指定 doc_id 开始（断点恢复）")
    parser.add_argument("--only-flat", action="store_true", help="只处理当前 max_level=1 的文档")
    parser.add_argument("--limit",     type=int,         default=0,  help="最多处理 N 个文档（测试用）")
    args = parser.parse_args()

    init_db()
    driver = get_driver()

    docs = fetch_docs(driver, only_flat=args.only_flat)

    # --from 筛选
    if args.from_doc:
        idx = next((i for i, d in enumerate(docs) if d["doc_id"] >= args.from_doc), 0)
        docs = docs[idx:]

    # --limit 截断
    if args.limit > 0:
        docs = docs[: args.limit]

    total_docs = len(docs)

    # ── dry-run ──────────────────────────────────────────────────────────────
    if args.dry_run:
        before_total, before_levels = section_stats(driver)

        # 统计 invalid / 无 storage_key 的跳过数
        with driver.session() as s:
            skipped = s.run("""
                MATCH (d:Document)
                WHERE d.storage_key IS NULL OR coalesce(d.status,'') = 'invalid'
                RETURN count(d) AS n
            """).single()["n"]

        level_dist = {}
        for d in docs:
            lv = str(d["max_level"])
            level_dist[lv] = level_dist.get(lv, 0) + 1

        # 估算：假设平均每个文档 4 秒
        avg_sec_per_doc = 4
        eta_sec = total_docs * avg_sec_per_doc
        eta_min = eta_sec // 60

        print("\n" + "━" * 58)
        print("  dry-run 统计（不会修改任何数据）")
        print("━" * 58)
        print(f"  待处理文档数：  {total_docs}")
        print(f"  跳过（invalid）：{skipped}")
        if args.from_doc:
            print(f"  起始文档：     {args.from_doc}")
        if args.limit:
            print(f"  限制数量：     {args.limit}")
        if args.only_flat:
            print(f"  仅处理 max_level=1")
        print(f"\n  当前 Section 总数：{before_total}")
        print(f"  当前层级分布：  {before_levels}")
        print(f"\n  当前文档层级分布（max_level）：")
        for lv in sorted(level_dist):
            print(f"    level={lv}: {level_dist[lv]} 个文档")
        print(f"\n  预计耗时：约 {eta_min} 分钟（按 {avg_sec_per_doc}s/文档估算）")
        print(f"\n  进度文件：{PROGRESS_FILE}")
        print("━" * 58)
        print("  确认后去掉 --dry-run 即可正式运行")
        print("━" * 58 + "\n")
        driver.close()
        return

    # ── 正式运行 ─────────────────────────────────────────────────────────────
    before_total, before_levels = section_stats(driver)
    progress  = load_progress()
    done_set  = set(progress.get("completed", []))
    failed    = dict(progress.get("failed", {}))

    ok_count   = 0
    fail_count = 0
    skip_count = 0
    timings: list[float] = []

    print(f"\n开始处理 {total_docs} 个文档（已完成 {len(done_set)} 个）…\n")

    for seq, doc in enumerate(docs, 1):
        doc_id      = doc["doc_id"]
        storage_key = doc["storage_key"]

        if doc_id in done_set:
            skip_count += 1
            continue

        t0 = time.time()
        try:
            sections = parse_doc(storage_key, doc_id)
            if not sections:
                raise ValueError("解析结果为空（0 章节）")

            neo4j_rewrite_sections(driver, doc_id, sections)
            elapsed = time.time() - t0
            timings.append(elapsed)

            done_set.add(doc_id)
            ok_count += 1

            # ── 每5个输出进度 ─────────────────────────────────────────────
            if ok_count % 5 == 0 or seq == total_docs:
                avg   = sum(timings) / len(timings)
                remaining = total_docs - seq - skip_count
                eta_s = avg * remaining
                eta_m = int(eta_s // 60)
                print(
                    f"  [{seq}/{total_docs}] {doc_id} ✓ {len(sections)}章节 "
                    f" 耗时{elapsed:.1f}s  预计剩余约{eta_m}分钟"
                )

        except Exception as e:
            elapsed = time.time() - t0
            msg = str(e)[:200]
            logger.warning("[%d/%d] %s 失败: %s", seq, total_docs, doc_id, msg)
            failed[doc_id] = msg
            fail_count += 1

        # 每5个保存一次进度
        if (ok_count + fail_count) % 5 == 0:
            save_progress({
                "completed":  sorted(done_set),
                "failed":     failed,
                "started_at": progress.get("started_at", ""),
            })

    # 最终保存
    save_progress({
        "completed":  sorted(done_set),
        "failed":     failed,
        "started_at": progress.get("started_at", ""),
    })

    after_total, after_levels = section_stats(driver)

    # ── 统计报告 ──────────────────────────────────────────────────────────────
    print("\n" + "━" * 58)
    print("  处理完成")
    print("━" * 58)
    print(f"  ✓ 成功：{ok_count + skip_count} 个（本次 {ok_count} 个，断点跳过 {skip_count} 个）")
    print(f"  ✗ 失败：{fail_count} 个（见 {PROGRESS_FILE}）")
    print(f"\n  Section 变化：{before_total} → {after_total}（{after_total - before_total:+d}）")
    print(f"\n  层级分布（修复后）：")
    for lv in sorted(after_levels):
        before = before_levels.get(lv, 0)
        after  = after_levels[lv]
        print(f"    level={lv}: {after} 个  （之前 {before}，{after - before:+d}）")
    if failed:
        print(f"\n  失败文档（前20条）：")
        for d, err in list(failed.items())[:20]:
            print(f"    {d}: {err[:80]}")
    print("━" * 58 + "\n")

    driver.close()


if __name__ == "__main__":
    main()
