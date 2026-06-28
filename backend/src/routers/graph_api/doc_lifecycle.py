"""
Document lifecycle and version management APIs.

GET  /api/graph/change-frequency    — Section 变更频率热力图
GET  /api/graph/valid-specs         — 查询某时间点有效的工艺规范
POST /api/admin/graph/set-validity  — 设置文档有效期
GET  /api/admin/graph/obsolescence-scan — 扫描废止文档引用告警
POST /api/graph/section-diff        — 生成两版本章节 Myers Diff 并写入图谱
"""
from __future__ import annotations

import asyncio
import difflib
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...auth.deps import get_admin_user, get_current_user
from ...core.database import get_driver
from ...db.models import User
from ...services.monitoring.alert_sender import AlertSender

log = logging.getLogger(__name__)
router = APIRouter(tags=["doc-lifecycle"])

_alert = AlertSender()


# ---------------------------------------------------------------------------
# Change-frequency heatmap
# ---------------------------------------------------------------------------

def _change_frequency() -> list[dict]:
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (sec:Section)-[:HAS_CHANGE_RECORD]->(cr:ChangeRecord)
            WITH sec, count(cr) AS change_count
            RETURN sec.chunk_id AS chunk_id, sec.title AS title,
                   sec.doc_id AS doc_id, change_count
            ORDER BY change_count DESC
            LIMIT 100
        """)
        return [dict(r) for r in result]


@router.get("/api/graph/change-frequency")
async def change_frequency(
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return per-section change frequency for heatmap rendering.
    High-frequency sections may indicate immature or unstable processes.
    """
    rows = await asyncio.to_thread(_change_frequency)
    return {"count": len(rows), "sections": rows}


# ---------------------------------------------------------------------------
# Validity time window
# ---------------------------------------------------------------------------

@router.get("/api/graph/valid-specs")
async def valid_specs(
    as_of: str | None = Query(None, description="ISO datetime; defaults to now"),
    doc_id: str | None = Query(None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return specs valid at a given point in time.
    Filters by valid_from ≤ as_of ≤ valid_until (or NULL = open-ended).
    """
    ts = as_of or datetime.now(timezone.utc).isoformat()
    driver = get_driver()
    with driver.session() as s:
        extra = "AND doc.doc_id = $did " if doc_id else ""
        result = s.run(
            f"""
            MATCH (doc:Document)
            WHERE (doc.valid_from IS NULL OR doc.valid_from <= $ts)
              AND (doc.valid_until IS NULL OR doc.valid_until >= $ts)
              AND coalesce(doc.obsolete, false) = false
              {extra}
            RETURN doc.doc_id AS doc_id, doc.title AS title,
                   doc.valid_from AS valid_from, doc.valid_until AS valid_until,
                   doc.version AS version
            ORDER BY doc.doc_id
            LIMIT 200
            """,
            ts=ts, **{"did": doc_id} if doc_id else {},
        )
        docs = [dict(r) for r in result]
    return {"as_of": ts, "count": len(docs), "documents": docs}


class ValidityBody(BaseModel):
    doc_id:      str
    valid_from:  str | None = None   # ISO
    valid_until: str | None = None   # ISO


@router.post("/api/admin/graph/set-validity")
async def set_validity(
    body: ValidityBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Set valid_from / valid_until on a Document node."""
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MATCH (doc:Document {doc_id: $did})
            SET doc.valid_from = $vf, doc.valid_until = $vu
        """, did=body.doc_id, vf=body.valid_from, vu=body.valid_until)
    return {"ok": True, "doc_id": body.doc_id,
            "valid_from": body.valid_from, "valid_until": body.valid_until}


# ---------------------------------------------------------------------------
# Obsolescence scan
# ---------------------------------------------------------------------------

def _scan_obsolescence() -> list[dict]:
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (old:Document)<-[:OBSOLETED_BY]-(new:Document)
            MATCH (ref:Document)-[:REFERENCES]->(old)
            WHERE ref.doc_id <> new.doc_id
            RETURN old.doc_id AS obsolete_doc, new.doc_id AS superseded_by,
                   collect(ref.doc_id) AS still_referenced_by
        """)
        return [dict(r) for r in result]


@router.get("/api/admin/graph/obsolescence-scan")
async def obsolescence_scan(
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """
    Scan for REFERENCES edges pointing to obsoleted documents.
    Triggers WARN alerts for each stale reference found.
    """
    stale = await asyncio.to_thread(_scan_obsolescence)
    for item in stale:
        await _alert.send(
            f"[WARN] 废止文档被引用: {item['obsolete_doc']} 已被 {item['superseded_by']} 取代，"
            f"但仍被 {len(item['still_referenced_by'])} 份文档引用",
            level="warning",
        )
    return {"stale_count": len(stale), "stale_references": stale}


# ---------------------------------------------------------------------------
# Section-level Myers Diff
# ---------------------------------------------------------------------------

class SectionDiffBody(BaseModel):
    chunk_id_old: str
    chunk_id_new: str
    write_to_graph: bool = True


def _fetch_content(chunk_id: str) -> str:
    driver = get_driver()
    with driver.session() as s:
        row = s.run(
            "MATCH (s:Section {chunk_id: $c}) RETURN s.content AS content", c=chunk_id
        ).single()
        return (row["content"] or "") if row else ""


def _write_diff_edge(old_id: str, new_id: str, diff_patch: str) -> None:
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MATCH (old:Section {chunk_id: $old}), (new:Section {chunk_id: $new})
            MERGE (old)-[r:CHANGED_TO]->(new)
            SET r.diff_patch = $patch,
                r.computed_at = $ts
        """, old=old_id, new=new_id, patch=diff_patch,
            ts=datetime.now(timezone.utc).isoformat())


@router.post("/api/graph/section-diff")
async def section_diff(
    body: SectionDiffBody,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Generate a unified Myers diff between two section versions.
    Optionally writes a CHANGED_TO edge with the diff patch to Neo4j.
    """
    old_text, new_text = await asyncio.gather(
        asyncio.to_thread(_fetch_content, body.chunk_id_old),
        asyncio.to_thread(_fetch_content, body.chunk_id_new),
    )
    if not old_text and not new_text:
        raise HTTPException(status_code=404, detail="One or both chunk_ids not found")

    diff_lines = list(difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=body.chunk_id_old,
        tofile=body.chunk_id_new,
        n=3,
    ))
    patch = "".join(diff_lines)

    if body.write_to_graph and patch:
        await asyncio.to_thread(_write_diff_edge, body.chunk_id_old, body.chunk_id_new, patch)

    stats = {
        "additions": sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++")),
        "deletions": sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---")),
    }
    return {
        "chunk_id_old": body.chunk_id_old,
        "chunk_id_new": body.chunk_id_new,
        "patch":        patch,
        "stats":        stats,
        "written_to_graph": body.write_to_graph and bool(patch),
    }
