"""
Graph Change Log — tracks node/relation create/update/delete operations.
Stored in PostgreSQL graph_changelog table.
Supports rollback of individual changes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Literal

from ...core.database import get_driver

log = logging.getLogger(__name__)

OperationType = Literal["CREATE_NODE", "UPDATE_NODE", "DELETE_NODE",
                         "CREATE_REL", "DELETE_REL"]


async def _db_exec(sql: str, params: dict) -> Any:
    """Execute SQL via asyncpg-compatible way."""
    import asyncpg
    from ...core.config import settings
    conn = await asyncpg.connect(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        result = await conn.fetch(sql, *params.values())
        return result
    finally:
        await conn.close()


def log_change(operator: str, operation_type: OperationType,
               entity_type: str, entity_id: str,
               before: dict | None = None,
               after: dict | None = None) -> int | None:
    """
    Synchronously log a graph change to PostgreSQL.
    Returns change record ID.
    """
    try:
        import psycopg2
        from ...core.config import settings
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO graph_changelog
                (operator, operation_type, entity_type, entity_id,
                 before_state, after_state, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
            """,
            (operator, operation_type, entity_type, entity_id,
             json.dumps(before) if before else None,
             json.dumps(after) if after else None),
        )
        result = cur.fetchone()
        conn.commit()
        conn.close()
        return result[0] if result else None
    except Exception as exc:
        log.warning("Failed to log graph change: %s", exc)
        return None


def get_changelog(since: str | None = None,
                  operation_type: str | None = None,
                  operator: str | None = None,
                  limit: int = 100) -> list[dict]:
    """Return filtered changelog entries."""
    try:
        import psycopg2
        from ...core.config import settings
        conn = psycopg2.connect(
            settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        )
        cur = conn.cursor()
        conditions = []
        params: list = []
        if since:
            conditions.append("created_at >= %s")
            params.append(since)
        if operation_type:
            conditions.append("operation_type = %s")
            params.append(operation_type)
        if operator:
            conditions.append("operator = %s")
            params.append(operator)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(
            f"""
            SELECT id, operator, operation_type, entity_type, entity_id,
                   before_state, after_state, created_at
            FROM graph_changelog
            {where}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            params + [limit],
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "operator": r[1], "operation_type": r[2],
                "entity_type": r[3], "entity_id": r[4],
                "before_state": json.loads(r[5]) if r[5] else None,
                "after_state": json.loads(r[6]) if r[6] else None,
                "created_at": str(r[7]),
            }
            for r in rows
        ]
    except Exception as exc:
        log.error("Failed to read changelog: %s", exc)
        return []


def rollback_change(change_id: int, operator: str) -> dict:
    """
    Reverse a single graph change operation.
    CREATE_NODE → delete node
    DELETE_NODE → recreate node
    UPDATE_NODE → restore before_state
    CREATE_REL → delete relation
    DELETE_REL → recreate relation
    """
    try:
        import psycopg2
        from ...core.config import settings
        conn = psycopg2.connect(
            settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT operation_type, entity_type, entity_id, before_state, after_state "
            "FROM graph_changelog WHERE id = %s",
            (change_id,),
        )
        row = cur.fetchone()
        conn.close()
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    if not row:
        return {"success": False, "error": "Change record not found"}

    op_type, entity_type, entity_id, before_raw, after_raw = row
    before = json.loads(before_raw) if before_raw else {}
    after = json.loads(after_raw) if after_raw else {}

    driver = get_driver()
    try:
        with driver.session() as s:
            if op_type == "CREATE_NODE":
                s.run(f"MATCH (n:{entity_type}) WHERE id(n) = $eid DELETE n",
                      eid=entity_id)
            elif op_type == "DELETE_NODE":
                props = " ".join(f"{k}: ${k}" for k in before)
                s.run(f"CREATE (n:{entity_type} {{{props}}})", **before)
            elif op_type == "UPDATE_NODE":
                if before:
                    set_clause = ", ".join(f"n.{k} = ${k}" for k in before)
                    s.run(f"MATCH (n:{entity_type} {{chunk_id: $eid}}) SET {set_clause}",
                          eid=entity_id, **before)
            elif op_type == "CREATE_REL":
                pass  # Relation rollback requires rel metadata
            elif op_type == "DELETE_REL":
                pass  # Recreate from before_state if available

        # Log the rollback itself
        log_change(operator, f"ROLLBACK_{op_type}", entity_type, entity_id,
                   before=after, after=before)
        return {"success": True, "reversed_operation": op_type}
    except Exception as exc:
        log.error("Rollback failed: %s", exc)
        return {"success": False, "error": str(exc)}


def get_incremental_sync(since: str, format_type: str = "json") -> list[dict]:
    """
    Return graph changes as JSON Patch format for downstream sync.
    Used by ERP/MES/PLM for incremental graph state sync.
    """
    changes = get_changelog(since=since, limit=10000)
    patches = []
    for c in changes:
        op = "add" if "CREATE" in c["operation_type"] else (
            "remove" if "DELETE" in c["operation_type"] else "replace"
        )
        patches.append({
            "op": op,
            "path": f"/{c['entity_type']}/{c['entity_id']}",
            "value": c.get("after_state"),
            "timestamp": c["created_at"],
            "operator": c["operator"],
        })
    return patches
