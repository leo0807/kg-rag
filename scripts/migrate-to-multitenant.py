#!/usr/bin/env python3
"""
G1.3 多租户迁移脚本 — 幂等、可重复执行
1. 创建 tenants / tenant_quotas / tenant_usage / plans / subscriptions / bills 表
2. 插入默认租户
3. 为各业务表添加 tenant_id 列（若不存在）
4. 将历史数据关联到默认租户
"""
import asyncio
import logging
import os
import sys
from datetime import date

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# 需要添加 tenant_id 的表
TENANT_TABLES = [
    "users",
    "conversations",
    "audit_logs",
    "favorites",
    "user_notes",
    "eval_datasets",
    "eval_runs",
    "generation_tasks",
    "spec_templates",
    "tenant_quotas",
]

DDL_TENANTS = """
CREATE TABLE IF NOT EXISTS tenants (
    id            VARCHAR(36) PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    slug          VARCHAR(100) UNIQUE NOT NULL,
    contact_name  VARCHAR(100),
    contact_email VARCHAR(200),
    contact_phone VARCHAR(50),
    status        VARCHAR(20)  DEFAULT 'active',
    plan          VARCHAR(50)  DEFAULT 'free',
    trial_ends_at        TIMESTAMP,
    subscription_ends_at TIMESTAMP,
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW(),
    settings      JSONB DEFAULT '{}'::jsonb,
    tenant_metadata JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_tenant_slug   ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenants(status);
"""

DDL_QUOTAS = """
CREATE TABLE IF NOT EXISTS tenant_quotas (
    tenant_id               VARCHAR(36) PRIMARY KEY,
    max_users               INT DEFAULT 10,
    max_documents           INT DEFAULT 100,
    max_storage_mb          INT DEFAULT 5000,
    max_queries_per_month   INT DEFAULT 10000,
    max_llm_tokens_per_month INT DEFAULT 5000000,
    max_evals_per_month     INT DEFAULT 50,
    rate_limit_per_minute   INT DEFAULT 60,
    rate_limit_per_hour     INT DEFAULT 1000,
    features JSONB DEFAULT '{"agent_mode":true,"multi_hop":true,"spec_generation":false,"evaluation":true,"advanced_search":true}'::jsonb,
    updated_at TIMESTAMP DEFAULT NOW()
);
"""

DDL_USAGE = """
CREATE TABLE IF NOT EXISTS tenant_usage (
    id           VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    tenant_id    VARCHAR(36) NOT NULL,
    period       VARCHAR(7)  NOT NULL,
    queries_count   INT DEFAULT 0,
    llm_tokens_used BIGINT DEFAULT 0,
    storage_used_mb INT DEFAULT 0,
    documents_count INT DEFAULT 0,
    users_count     INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, period)
);
CREATE INDEX IF NOT EXISTS idx_tenant_usage_tenant ON tenant_usage(tenant_id);
"""

DDL_PLANS = """
CREATE TABLE IF NOT EXISTS plans (
    id                       VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    name                     VARCHAR(50) UNIQUE NOT NULL,
    display_name             VARCHAR(100) DEFAULT '',
    max_users                INT,
    max_documents            INT,
    max_storage_mb           INT,
    max_queries_per_month    INT,
    max_llm_tokens_per_month INT,
    features                 JSONB DEFAULT '{}'::jsonb,
    monthly_price_cny        NUMERIC(10,2),
    yearly_price_cny         NUMERIC(10,2),
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

DDL_SUBSCRIPTIONS = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id           VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    tenant_id    VARCHAR(36) NOT NULL,
    plan_id      VARCHAR(36) NOT NULL,
    start_date   DATE,
    end_date     DATE,
    status       VARCHAR(20) DEFAULT 'active',
    auto_renew   BOOLEAN DEFAULT FALSE,
    period       VARCHAR(10) DEFAULT 'monthly',
    amount_paid  NUMERIC(10,2),
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subscription_tenant ON subscriptions(tenant_id);
"""

DDL_BILLS = """
CREATE TABLE IF NOT EXISTS bills (
    id             VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    tenant_id      VARCHAR(36) NOT NULL,
    billing_period VARCHAR(7)  NOT NULL,
    base_amount    NUMERIC(10,2) DEFAULT 0,
    overage_amount NUMERIC(10,2) DEFAULT 0,
    discount       NUMERIC(10,2) DEFAULT 0,
    total_amount   NUMERIC(10,2) DEFAULT 0,
    status     VARCHAR(20) DEFAULT 'pending',
    details    JSONB DEFAULT '{}'::jsonb,
    paid_at    TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bill_tenant_period ON bills(tenant_id, billing_period);
"""


async def column_exists(conn, table: str, col: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=$1 AND column_name=$2", table, col
    )
    return row is not None


async def table_exists(conn, table: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM information_schema.tables WHERE table_name=$1", table
    )
    return row is not None


async def run(dsn: str):
    conn = await asyncpg.connect(dsn)
    try:
        log.info("创建多租户核心表 …")
        await conn.execute(DDL_TENANTS)
        await conn.execute(DDL_QUOTAS)
        await conn.execute(DDL_USAGE)
        await conn.execute(DDL_PLANS)
        await conn.execute(DDL_SUBSCRIPTIONS)
        await conn.execute(DDL_BILLS)

        log.info("插入默认租户 …")
        await conn.execute("""
            INSERT INTO tenants(id, name, slug, status, plan)
            VALUES($1, '默认租户', 'default', 'active', 'enterprise')
            ON CONFLICT(id) DO NOTHING
        """, DEFAULT_TENANT_ID)

        await conn.execute("""
            INSERT INTO tenant_quotas(tenant_id, max_users, max_documents, max_storage_mb,
                max_queries_per_month, max_llm_tokens_per_month)
            VALUES($1, 99999, 99999, 999999, 999999, 999999999)
            ON CONFLICT(tenant_id) DO NOTHING
        """, DEFAULT_TENANT_ID)

        log.info("为业务表添加 tenant_id 列 …")
        for tbl in TENANT_TABLES:
            if not await table_exists(conn, tbl):
                log.warning("  表 %s 不存在，跳过", tbl)
                continue
            if not await column_exists(conn, tbl, "tenant_id"):
                await conn.execute(f'ALTER TABLE "{tbl}" ADD COLUMN tenant_id VARCHAR(36)')
                await conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{tbl}_tenant ON "{tbl}"(tenant_id)')
                log.info("  + %s.tenant_id", tbl)
            else:
                log.info("  已存在 %s.tenant_id，跳过", tbl)

        # 添加 users.is_platform_admin 列
        if await table_exists(conn, "users"):
            if not await column_exists(conn, "users", "is_platform_admin"):
                await conn.execute("ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN DEFAULT FALSE")
                log.info("  + users.is_platform_admin")

        log.info("将历史数据关联到默认租户 …")
        for tbl in TENANT_TABLES:
            if not await table_exists(conn, tbl):
                continue
            if not await column_exists(conn, tbl, "tenant_id"):
                continue
            n = await conn.fetchval(
                f'UPDATE "{tbl}" SET tenant_id=$1 WHERE tenant_id IS NULL RETURNING COUNT(*)',
                DEFAULT_TENANT_ID,
            ) or await conn.fetchval(
                f'SELECT COUNT(*) FROM "{tbl}" WHERE tenant_id=$1', DEFAULT_TENANT_ID
            )
            log.info("  %s: %s 行已关联默认租户", tbl, n)

        log.info("✅ 迁移完成")
    finally:
        await conn.close()


if __name__ == "__main__":
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")
    if not db_url:
        print("请设置 DATABASE_URL 或 POSTGRES_DSN 环境变量", file=sys.stderr)
        sys.exit(1)
    # asyncpg 使用 postgresql:// 而非 postgresql+asyncpg://
    dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")
    asyncio.run(run(dsn))
