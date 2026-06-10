"""F3.2 — Lifecycle runner: enforces data retention policies."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.lifecycle_models import DataRetentionPolicy
from ...db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Default policies seeded on first run (resource_type → retention_days)
_DEFAULTS = {
    "audit_event":   365,
    "query_session": 180,
    "query_log":     90,
    "temp_export":   7,
}

# Maps resource_type → (table_name, timestamp_column)
_TABLE_MAP = {
    "audit_event":   ("audit_events",    "timestamp"),
    "query_session": ("query_sessions",  "updated_at"),
    "query_log":     ("query_feedback",  "created_at"),
}


async def seed_default_policies(db: AsyncSession) -> None:
    for rtype, days in _DEFAULTS.items():
        existing = (await db.execute(
            select(DataRetentionPolicy).where(DataRetentionPolicy.resource_type == rtype)
        )).scalar_one_or_none()
        if not existing:
            db.add(DataRetentionPolicy(resource_type=rtype, retention_days=days))
    await db.commit()


async def run_lifecycle() -> dict[str, int]:
    """Execute all active retention policies. Returns {resource_type: deleted_count}."""
    results: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        policies = (await db.execute(
            select(DataRetentionPolicy).where(DataRetentionPolicy.is_active == True)  # noqa: E712
        )).scalars().all()

        for policy in policies:
            table_info = _TABLE_MAP.get(policy.resource_type)
            if not table_info:
                continue
            table, ts_col = table_info
            cutoff = datetime.now(timezone.utc) - timedelta(days=policy.retention_days)
            try:
                result = await db.execute(
                    text(f"DELETE FROM {table} WHERE {ts_col} < :cutoff RETURNING id"),
                    {"cutoff": cutoff},
                )
                deleted = result.rowcount
                await db.execute(
                    text("UPDATE data_retention_policies SET last_run_at = NOW(), "
                         "last_run_deleted = :n WHERE id = :id"),
                    {"n": deleted, "id": policy.id},
                )
                await db.commit()
                results[policy.resource_type] = deleted
                logger.info("Lifecycle: deleted %d rows from %s (policy: %d days)",
                            deleted, table, policy.retention_days)
            except Exception as e:
                logger.warning("Lifecycle error for %s: %s", policy.resource_type, e)
                await db.rollback()
    return results
