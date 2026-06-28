"""
Storage capacity monitoring.

GET /api/admin/storage/stats — 各存储组件容量快照 + Top-10 文档占用
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User
from ...db.session import get_db
from ...services.monitoring.alert_sender import AlertSender
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/storage", tags=["admin-storage"])

UPLOAD_DIR   = os.getenv("UPLOAD_DIR", "uploads")
WARN_RATIO   = float(os.getenv("STORAGE_WARN_RATIO", "0.8"))

_sender = AlertSender()


async def _neo4j_stats() -> dict[str, Any]:
    try:
        driver = get_driver()
        with driver.session() as s:
            row = s.run(
                "CALL apoc.meta.stats() YIELD nodeCount, relCount, labels, relTypesCount"
                " RETURN nodeCount, relCount, labels, relTypesCount"
            ).single()
            if row:
                return {
                    "node_count": row["nodeCount"],
                    "rel_count":  row["relCount"],
                    "label_breakdown": dict(row["labels"]),
                }
    except Exception:
        # APOC not installed — fall back to basic count
        try:
            with get_driver().session() as s:
                nc = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                rc = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                return {"node_count": nc, "rel_count": rc}
        except Exception as exc:
            log.debug("neo4j stats failed: %s", exc)
    return {}


async def _milvus_stats() -> dict[str, Any]:
    try:
        from pymilvus import connections, utility  # noqa: PLC0415

        host = os.getenv("MILVUS_HOST", "localhost")
        port = int(os.getenv("MILVUS_PORT", "19530"))
        connections.connect(alias="default", host=host, port=port)
        collections = utility.list_collections()
        stats: dict[str, Any] = {"collections": {}}
        total = 0
        for col in collections:
            from pymilvus import Collection  # noqa: PLC0415
            c = Collection(col)
            cnt = c.num_entities
            total += cnt
            stats["collections"][col] = cnt
        stats["total_vectors"] = total
        return stats
    except Exception as exc:
        log.debug("milvus stats failed: %s", exc)
        return {}


async def _postgres_stats(db: AsyncSession) -> dict[str, Any]:
    try:
        rows = await db.execute(text("""
            SELECT relname AS table_name,
                   pg_total_relation_size(relid) AS total_bytes,
                   pg_size_pretty(pg_total_relation_size(relid)) AS total_size
            FROM pg_catalog.pg_statio_user_tables
            ORDER BY total_bytes DESC
            LIMIT 20
        """))
        tables = [{"table": r[0], "size": r[2], "bytes": r[1]} for r in rows]
        total_bytes = await db.scalar(text(
            "SELECT pg_database_size(current_database())"
        ))
        return {"total_size_bytes": total_bytes, "tables": tables[:10]}
    except Exception as exc:
        log.debug("postgres stats failed: %s", exc)
        return {}


def _uploads_stats() -> dict[str, Any]:
    upload_path = Path(UPLOAD_DIR)
    if not upload_path.exists():
        return {"total_bytes": 0, "file_count": 0, "top_files": []}

    files = list(upload_path.rglob("*.pdf"))
    file_sizes = [(f, f.stat().st_size) for f in files if f.exists()]
    file_sizes.sort(key=lambda x: -x[1])
    total = sum(s for _, s in file_sizes)
    top10 = [
        {"name": str(f.name), "bytes": s, "size": _fmt_bytes(s)}
        for f, s in file_sizes[:10]
    ]
    return {"total_bytes": total, "file_count": len(files), "top_files": top10}


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


@router.get("/stats")
async def storage_stats(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Snapshot of storage capacity across all subsystems.
    Triggers an alert if any component exceeds WARN_RATIO of estimated capacity.
    """
    neo4j   = await _neo4j_stats()
    milvus  = await _milvus_stats()
    pg      = await _postgres_stats(db)
    uploads = _uploads_stats()

    # Warn if uploads dir > 80 % of 100 GB estimated quota
    upload_quota = int(os.getenv("UPLOAD_QUOTA_GB", "100")) * 1024 ** 3
    upload_ratio = uploads["total_bytes"] / max(upload_quota, 1)
    if upload_ratio >= WARN_RATIO:
        await _sender.send(
            f"[WARN] 文档存储已使用 {upload_ratio:.0%} "
            f"({_fmt_bytes(uploads['total_bytes'])} / {_fmt_bytes(upload_quota)})",
            level="warning",
        )

    return {
        "as_of":   datetime.now(timezone.utc).isoformat(),
        "neo4j":   neo4j,
        "milvus":  milvus,
        "postgres": pg,
        "uploads": {
            **uploads,
            "total_size": _fmt_bytes(uploads["total_bytes"]),
            "quota_ratio": round(upload_ratio, 4),
        },
    }
