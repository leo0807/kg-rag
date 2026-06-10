#!/usr/bin/env python3
"""
G7.2 租户隔离审计脚本
直接连接数据库，扫描各业务表的 tenant_id 覆盖率及潜在跨租户引用问题。
"""
import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

TABLES = [
    "users", "conversations", "audit_logs", "favorites", "user_notes",
    "eval_datasets", "eval_runs", "generation_tasks", "spec_templates",
    "tenant_usage", "bills", "subscriptions",
]


async def audit_table(conn: asyncpg.Connection, table: str) -> dict:
    col_exists = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=$1 AND column_name='tenant_id'", table
    )
    if not col_exists:
        return {"table": table, "status": "no_tenant_id_column", "issues": []}

    total = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"') or 0
    null_count = await conn.fetchval(f'SELECT COUNT(*) FROM "{table}" WHERE tenant_id IS NULL') or 0
    coverage = round((total - null_count) / max(total, 1) * 100, 1)

    issues = []
    if null_count > 0:
        issues.append(f"{null_count} 行 tenant_id 为 NULL")

    # 检查是否存在指向其他租户记录的外键（仅对有 user_id 的表）
    user_col = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns WHERE table_name=$1 AND column_name='user_id'", table
    )
    if user_col:
        cross = await conn.fetchval(f"""
            SELECT COUNT(*) FROM "{table}" t
            JOIN users u ON u.id = t.user_id
            WHERE t.tenant_id IS NOT NULL AND u.tenant_id IS NOT NULL
              AND t.tenant_id != u.tenant_id
        """) or 0
        if cross > 0:
            issues.append(f"⚠ {cross} 行与 users 租户不一致（跨租户引用）")

    status = "ok" if not issues else ("warning" if null_count < total else "critical")
    return {
        "table": table, "total": total, "null_count": null_count,
        "coverage_pct": coverage, "status": status, "issues": issues,
    }


async def run(dsn: str):
    conn = await asyncpg.connect(dsn)
    try:
        log.info("开始隔离审计 …")
        results = []
        for tbl in TABLES:
            try:
                exists = await conn.fetchval(
                    "SELECT 1 FROM information_schema.tables WHERE table_name=$1", tbl
                )
                if not exists:
                    log.info("  跳过（表不存在）: %s", tbl)
                    continue
                result = await audit_table(conn, tbl)
                results.append(result)
                icon = "✅" if result["status"] == "ok" else "⚠️"
                log.info("  %s %s: coverage=%.1f%% issues=%s",
                         icon, tbl, result.get("coverage_pct", 0), result.get("issues", []))
            except Exception as e:
                log.error("  错误 %s: %s", tbl, e)
                results.append({"table": tbl, "status": "error", "error": str(e)})

        total_issues = sum(len(r.get("issues", [])) for r in results)
        log.info("\n========== 审计摘要 ==========")
        log.info("检查表数: %d", len(results))
        log.info("发现问题: %d", total_issues)

        critical = [r for r in results if r.get("status") == "critical"]
        if critical:
            log.error("严重问题表: %s", [r["table"] for r in critical])
            sys.exit(1)
        elif total_issues > 0:
            log.warning("存在警告，建议运行迁移脚本修复")
            sys.exit(2)
        else:
            log.info("✅ 所有表隔离良好")
    finally:
        await conn.close()


if __name__ == "__main__":
    dsn = (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN") or "").replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    if not dsn:
        print("请设置 DATABASE_URL 或 POSTGRES_DSN", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run(dsn))
