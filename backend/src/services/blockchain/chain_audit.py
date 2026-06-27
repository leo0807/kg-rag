"""
Blockchain-backed document audit trail for AS9100 / NADCAP compliance.

Architecture:
  Default: SHA-256 hash-chain stored in PostgreSQL `chain_records` table.
    Each record hashes (doc_id + version + sha256_content + prev_hash + timestamp),
    forming a tamper-evident chain verifiable offline.

  Optional: FISCO BCOS adapter (domestic blockchain, activated via FISCO_NODE_URL env).
    Requires: pip install fisco-bcos-python-sdk

Usage:
    from .chain_audit import record_doc_change, get_chain_history

    # On document ingest / version change:
    await record_doc_change(doc_id="CPS-001", version="v2.1",
                            content_hash=sha256(content), operator="emp001")

    # Audit query:
    history = await get_chain_history("CPS-001")
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

DB_URL        = os.getenv("DATABASE_URL", "")
FISCO_NODE    = os.getenv("FISCO_NODE_URL", "")   # empty = local hash-chain only
CHAIN_TABLE   = "chain_records"


# ── PostgreSQL hash-chain (always available) ──────────────────────────────────

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {CHAIN_TABLE} (
    id            SERIAL PRIMARY KEY,
    doc_id        TEXT NOT NULL,
    version       TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    prev_hash     TEXT NOT NULL DEFAULT '',
    record_hash   TEXT NOT NULL,
    operator      TEXT NOT NULL DEFAULT '',
    tx_id         TEXT NOT NULL DEFAULT '',   -- FISCO BCOS tx hash if on-chain
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chain_doc ON {CHAIN_TABLE} (doc_id, created_at);
"""


def _compute_record_hash(
    doc_id: str, version: str, content_hash: str,
    prev_hash: str, operator: str, ts: str,
) -> str:
    payload = f"{doc_id}|{version}|{content_hash}|{prev_hash}|{operator}|{ts}"
    return hashlib.sha256(payload.encode()).hexdigest()


async def _get_prev_hash(conn, doc_id: str) -> str:
    row = await conn.fetchrow(
        f"SELECT record_hash FROM {CHAIN_TABLE} WHERE doc_id=$1 ORDER BY id DESC LIMIT 1",
        doc_id,
    )
    return row["record_hash"] if row else ""


async def record_doc_change(
    doc_id: str,
    version: str,
    content_hash: str,
    operator: str = "",
    extra: dict[str, Any] | None = None,
) -> dict:
    """
    Append a tamper-evident record to the chain for doc_id.
    Returns the new record dict including record_hash.
    """
    try:
        import asyncpg
    except ImportError:
        log.warning("asyncpg not installed — chain record skipped")
        return {}

    dsn = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(CREATE_TABLE_SQL)
        prev_hash = await _get_prev_hash(conn, doc_id)
        ts = datetime.now(timezone.utc).isoformat()
        record_hash = _compute_record_hash(doc_id, version, content_hash, prev_hash, operator, ts)

        tx_id = ""
        if FISCO_NODE:
            tx_id = await _write_fisco(doc_id, version, content_hash, record_hash, operator, ts)

        await conn.execute(
            f"""
            INSERT INTO {CHAIN_TABLE}
                (doc_id, version, content_hash, prev_hash, record_hash, operator, tx_id, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            doc_id, version, content_hash, prev_hash, record_hash, operator, tx_id, ts,
        )
        log.info("Chain record written: doc=%s v=%s hash=%s...", doc_id, version, record_hash[:12])
        return {
            "doc_id": doc_id, "version": version,
            "record_hash": record_hash, "tx_id": tx_id, "ts": ts,
        }
    finally:
        await conn.close()


async def get_chain_history(doc_id: str) -> list[dict]:
    """Return the full chain of records for a document, oldest first."""
    try:
        import asyncpg
    except ImportError:
        return []

    dsn = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            f"""
            SELECT doc_id, version, content_hash, prev_hash, record_hash,
                   operator, tx_id, created_at
            FROM {CHAIN_TABLE}
            WHERE doc_id = $1
            ORDER BY id ASC
            """,
            doc_id,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def verify_chain(records: list[dict]) -> bool:
    """Verify integrity of a chain: each record_hash must be reproducible from its fields."""
    for i, r in enumerate(records):
        expected_prev = records[i - 1]["record_hash"] if i > 0 else ""
        if r["prev_hash"] != expected_prev:
            log.error("Chain broken at index %d: prev_hash mismatch", i)
            return False
        expected_hash = _compute_record_hash(
            r["doc_id"], r["version"], r["content_hash"],
            r["prev_hash"], r["operator"],
            r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
        )
        if r["record_hash"] != expected_hash:
            log.error("Chain tampered at index %d: record_hash mismatch", i)
            return False
    return True


# ── FISCO BCOS adapter (optional) ─────────────────────────────────────────────

async def _write_fisco(
    doc_id: str, version: str, content_hash: str,
    record_hash: str, operator: str, ts: str,
) -> str:
    """Write record to FISCO BCOS chain; returns tx hash or empty string on error."""
    try:
        # fisco-bcos-python-sdk usage
        from client.bcosclient import BcosClient  # type: ignore

        client = BcosClient()
        payload = json.dumps({
            "doc_id": doc_id, "version": version,
            "sha256": content_hash, "timestamp": ts, "operator": operator,
        })
        result = client.sendRawTransaction("DocAudit", "recordChange", [payload])
        tx_hash = result.get("transactionHash", "")
        log.info("FISCO BCOS tx: %s", tx_hash)
        return tx_hash
    except Exception as exc:
        log.warning("FISCO BCOS write failed (local chain still written): %s", exc)
        return ""
