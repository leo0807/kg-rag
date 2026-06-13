"""
Schema sync: compare SQLAlchemy Base.metadata with live PostgreSQL and
apply ADD COLUMN IF NOT EXISTS for every missing column.

Called both from startup.init_tables() and scripts/schema-sync.py.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.dialects import postgresql as pg

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


def _pg_type(col) -> str:
    """Compile a SQLAlchemy column type to a PostgreSQL DDL string."""
    try:
        return col.type.compile(dialect=pg.dialect())
    except Exception:
        return "TEXT"


def _default_for_type(col) -> str | None:
    """Return a safe server-side DEFAULT for NOT NULL columns."""
    from sqlalchemy import types
    t = col.type
    if isinstance(t, (types.String, types.Text, types.Enum)):
        return "''"
    if isinstance(t, (types.Integer, types.BigInteger, types.SmallInteger)):
        return "0"
    if isinstance(t, types.Boolean):
        return "FALSE"
    if isinstance(t, (types.Float, types.Numeric)):
        return "0"
    if isinstance(t, types.JSON):
        return "'{}'::jsonb"
    return None


async def sync_schema(conn: "AsyncConnection") -> list[str]:
    """
    Inspect live DB and add any model columns that are absent.

    Returns a list of human-readable change descriptions.
    """
    from .base import Base  # noqa: F401 — triggers subclass registration
    # Import every model module so all tables are registered in Base.metadata.
    from . import (  # noqa: F401
        models, gen_models, ux_models, eval_models, rbac_models,
        lifecycle_models, version_models, tenant_models,
        integration_models, report_models, simulation_models,
    )
    try:
        from . import deployment_models  # noqa: F401
    except ImportError:
        pass
    try:
        from ..services.audit import audit_models  # noqa: F401
    except ImportError:
        pass
    try:
        from ..routers import feedback  # noqa: F401 — registers QueryFeedback
    except ImportError:
        pass

    # 1. Create tables that don't exist at all.
    await conn.run_sync(Base.metadata.create_all)

    # 2. For tables that already existed, add missing columns.
    result = await conn.execute(text(
        "SELECT table_name, column_name "
        "FROM information_schema.columns "
        "WHERE table_schema = 'public'"
    ))
    existing: dict[str, set[str]] = {}
    for tbl, col in result:
        existing.setdefault(tbl, set()).add(col)

    changes: list[str] = []
    for table in Base.metadata.sorted_tables:
        tbl_cols = existing.get(table.name, set())
        for col in table.columns:
            if col.name in tbl_cols:
                continue  # already present

            pg_type = _pg_type(col)

            # Build: ALTER TABLE t ADD COLUMN IF NOT EXISTS c TYPE [DEFAULT x] [NOT NULL]
            parts = [
                f"ALTER TABLE {table.name}",
                f"ADD COLUMN IF NOT EXISTS {col.name} {pg_type}",
            ]

            # Server default takes priority.
            if col.server_default is not None:
                sd = col.server_default.arg
                if not isinstance(sd, str):
                    sd = str(sd)
                parts.append(f"DEFAULT {sd}")
            elif not col.nullable:
                # NOT NULL column without server_default → supply a safe fallback.
                fallback = _default_for_type(col)
                if fallback:
                    parts.append(f"DEFAULT {fallback}")

            if not col.nullable:
                parts.append("NOT NULL")

            stmt = " ".join(parts)
            try:
                await conn.execute(text(stmt))
                msg = f"{table.name}.{col.name} [{pg_type}]"
                changes.append(msg)
                logger.info("schema_sync: + %s", msg)
            except Exception as exc:
                logger.warning("schema_sync: SKIP %s.%s — %s", table.name, col.name, exc)

    return changes


async def ensure_default_tenant(conn: "AsyncConnection") -> str:
    """
    Idempotently create a default tenant and return its id.
    Also back-fills NULL tenant_id on users/conversations/audit_logs.
    """
    DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
    DEFAULT_TENANT_SLUG = "default"

    row = await conn.execute(text(
        "SELECT id FROM tenants WHERE slug = :s"
    ), {"s": DEFAULT_TENANT_SLUG})
    existing = row.fetchone()
    if not existing:
        await conn.execute(text("""
            INSERT INTO tenants
              (id, name, slug, status, plan, settings, tenant_metadata)
            VALUES
              (:id, '默认租户', :slug, 'active', 'free', '{}', '{}')
            ON CONFLICT (slug) DO NOTHING
        """), {"id": DEFAULT_TENANT_ID, "slug": DEFAULT_TENANT_SLUG})
        logger.info("schema_sync: created default tenant %s", DEFAULT_TENANT_ID)
        tenant_id = DEFAULT_TENANT_ID
    else:
        tenant_id = existing[0]

    # Back-fill NULL tenant_id on core tables.
    for tbl in ("users", "conversations", "audit_logs"):
        try:
            await conn.execute(text(
                f"UPDATE {tbl} SET tenant_id = :tid WHERE tenant_id IS NULL"
            ), {"tid": tenant_id})
        except Exception:
            pass  # table might not have tenant_id yet (will be added by sync_schema)

    return tenant_id
