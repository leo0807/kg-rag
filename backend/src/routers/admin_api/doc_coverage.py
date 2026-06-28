"""
Document entity coverage report.

GET  /api/admin/documents/coverage-report — 各文档实体覆盖率排行
POST /api/admin/documents/{doc_id}/reanalyze — 批量触发实体重提取
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/documents", tags=["admin-doc-coverage"])

_LOW_COVERAGE_THRESHOLD = 0.30


def _coverage_query() -> list[dict]:
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (doc:Document)
            WITH doc
            OPTIONAL MATCH (doc)-[:HAS_SECTION]->(sec:Section)
            WITH doc, count(sec) AS total_sections
            OPTIONAL MATCH (doc)-[:HAS_SECTION]->(sec2:Section)
            WHERE (sec2)-[:REQUIRES_TOOL]->() OR (sec2)-[:USES_MATERIAL]->()
                  OR (sec2)-[:INVOLVES_PROCESS]->()
            WITH doc, total_sections, count(DISTINCT sec2) AS covered_sections
            RETURN doc.doc_id AS doc_id,
                   doc.title  AS title,
                   total_sections,
                   covered_sections,
                   CASE WHEN total_sections > 0
                        THEN toFloat(covered_sections) / total_sections
                        ELSE 0 END AS coverage_ratio
            ORDER BY coverage_ratio ASC
            LIMIT 100
        """)
        return [dict(r) for r in result]


def _reanalyze_doc(doc_id: str) -> None:
    """Re-run entity extraction for sections in a document."""
    try:
        driver = get_driver()
        with driver.session() as s:
            chunks = s.run(
                "MATCH (doc:Document {doc_id: $d})-[:HAS_SECTION]->(s:Section) "
                "RETURN s.chunk_id AS chunk_id LIMIT 200",
                d=doc_id,
            )
            chunk_ids = [r["chunk_id"] for r in chunks]
        if not chunk_ids:
            return

        from ...tasks.entity_tasks import extract_entities_for_chunk  # noqa: PLC0415
        for cid in chunk_ids:
            try:
                extract_entities_for_chunk(cid)
            except Exception as exc:
                log.warning("reanalyze chunk %s: %s", cid, exc)
    except Exception as exc:
        log.error("reanalyze_doc %s: %s", doc_id, exc)


@router.get("/coverage-report")
async def coverage_report(
    min_sections: int = Query(default=1, ge=1, description="Minimum sections to include doc"),
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """
    Return entity coverage ratio per document.
    Documents with coverage < 30% are flagged as 'entity_extraction_incomplete'.
    """
    import asyncio  # noqa: PLC0415

    rows = await asyncio.to_thread(_coverage_query)
    rows = [r for r in rows if (r.get("total_sections") or 0) >= min_sections]

    enriched = [
        {
            **r,
            "coverage_ratio":  round(r.get("coverage_ratio") or 0, 4),
            "status": (
                "entity_extraction_incomplete"
                if (r.get("coverage_ratio") or 0) < _LOW_COVERAGE_THRESHOLD
                else "ok"
            ),
        }
        for r in rows
    ]

    incomplete = [r for r in enriched if r["status"] == "entity_extraction_incomplete"]

    return {
        "total_docs":    len(enriched),
        "incomplete":    len(incomplete),
        "threshold":     _LOW_COVERAGE_THRESHOLD,
        "documents":     enriched,
    }


@router.post("/{doc_id}/reanalyze")
async def reanalyze_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Trigger entity re-extraction for all sections of a document."""
    background_tasks.add_task(_reanalyze_doc, doc_id)
    return {"ok": True, "doc_id": doc_id, "status": "queued"}
