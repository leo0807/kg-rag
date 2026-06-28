"""
MES (Manufacturing Execution System) integration endpoints.

GET /api/mes/procedure?work_order_id=  — Return process steps for a work order
POST /api/mes/completion               — Record step completion from MES
GET /api/mes/work-orders               — List active work orders with linked specs
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth.deps import get_current_user
from ..core.database import get_driver
from ..db.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mes", tags=["mes"])

MES_BASE_URL = os.getenv("MES_BASE_URL", "")
MES_API_KEY  = os.getenv("MES_API_KEY", "")


class CompletionRequest(BaseModel):
    work_order_id: str
    step_order:    int
    operator_id:   str = ""
    result:        str = "pass"  # pass | fail | rework
    notes:         str = ""


async def _fetch_mes_work_order(work_order_id: str) -> dict | None:
    """Pull work order details from the MES system (if configured)."""
    if not MES_BASE_URL:
        return None
    headers = {"X-API-Key": MES_API_KEY} if MES_API_KEY else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{MES_BASE_URL}/api/work-orders/{work_order_id}",
                headers=headers,
            )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("MES fetch failed: %s", exc)
        return None


@router.get("/procedure")
async def get_mes_procedure(
    work_order_id: str = Query(..., description="MES 工单编号"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return the process procedure for a MES work order.

    Looks up the work order in MES (if configured) to find the associated
    process specification, then retrieves the steps, tools, and quality
    requirements from the knowledge graph.

    Callers: MES scanners, tablet apps on the shop floor.
    """
    driver = get_driver()

    # Try MES to get the linked spec doc_id
    mes_data = await _fetch_mes_work_order(work_order_id)
    spec_doc_id: str | None = None
    if mes_data:
        spec_doc_id = mes_data.get("spec_doc_id") or mes_data.get("process_spec")

    with driver.session() as s:
        if spec_doc_id:
            # Fetch sections of the linked spec
            result = s.run(
                """
                MATCH (doc:Document {name: $doc_id})-[:HAS_SECTION]->(sec:Section)
                RETURN sec.chunk_id AS chunk_id, sec.title AS title,
                       sec.content AS content, sec.doc_id AS doc_id
                ORDER BY sec.chunk_id
                LIMIT 30
                """,
                doc_id=spec_doc_id,
            )
        else:
            # Fallback: search by work_order_id string
            result = s.run(
                """
                MATCH (sec:Section)
                WHERE sec.content CONTAINS $wo_id OR sec.doc_id CONTAINS $wo_id
                RETURN sec.chunk_id AS chunk_id, sec.title AS title,
                       sec.content AS content, sec.doc_id AS doc_id
                LIMIT 10
                """,
                wo_id=work_order_id,
            )
        sections = [dict(r) for r in result]

    # For each section, get steps and tools
    procedures = []
    for sec in sections[:5]:
        cid = sec["chunk_id"]
        tools_r = s.run(
            "MATCH (s:Section {chunk_id: $c})-[:REQUIRES_TOOL]->(t:Tool) RETURN t.name AS name LIMIT 5",
            c=cid,
        )
        tools = [r["name"] for r in tools_r]
        procedures.append({
            "chunk_id": cid,
            "title":    sec["title"],
            "doc_id":   sec["doc_id"],
            "summary":  (sec.get("content") or "")[:300],
            "tools":    tools,
        })

    return {
        "work_order_id": work_order_id,
        "spec_doc_id":   spec_doc_id or "unknown",
        "procedure_count": len(procedures),
        "procedures":    procedures,
        "mes_data":      mes_data,
    }


@router.post("/completion")
async def record_mes_completion(
    body: CompletionRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Record step completion in Neo4j and optionally relay to MES.
    Called by the AR interface after a worker confirms a step.
    """
    driver = get_driver()
    with driver.session() as s:
        s.run(
            """
            MERGE (sc:WorkOrderStep {
                work_order_id: $wo_id, step_order: $step
            })
            SET sc.result      = $result,
                sc.operator_id = $op,
                sc.notes       = $notes,
                sc.recorded_at = datetime()
            """,
            wo_id=body.work_order_id,
            step=body.step_order,
            result=body.result,
            op=body.operator_id or str(user.id),
            notes=body.notes,
        )

    # Relay to MES if configured
    if MES_BASE_URL:
        headers = {"X-API-Key": MES_API_KEY} if MES_API_KEY else {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{MES_BASE_URL}/api/step-completions",
                    json=body.model_dump(),
                    headers=headers,
                )
        except Exception as exc:
            log.warning("MES relay failed: %s", exc)

    return {"ok": True, "work_order_id": body.work_order_id, "step_order": body.step_order}
