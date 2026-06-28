"""
AR / WebXR assembly-assistance endpoints.

GET  /api/ar/lookup?barcode=     — barcode → process section info
GET  /api/ar/steps/{chunk_id}   — ordered work steps for a section
POST /api/ar/step-complete      — record step completion (writes to MES + graph)
GET  /api/ar/overlay/{chunk_id} — full AR overlay data (steps + tools + warnings)
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
router = APIRouter(prefix="/api/ar", tags=["ar"])

MES_WEBHOOK_URL = os.getenv("MES_WEBHOOK_URL", "")


class StepCompleteRequest(BaseModel):
    chunk_id:       str
    step_order:     int
    work_order_id:  str = ""
    operator_id:    str = ""
    notes:          str = ""


@router.get("/lookup")
async def ar_lookup(
    barcode: str = Query(..., description="零件条形码或 P/N 编号"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Scan a part barcode and return all related process sections.

    The barcode is matched against Neo4j Component nodes (part_no field).
    Returns applicable sections with their titles, doc_id, and chunk_id.
    """
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (comp:Component {part_no: $barcode})<-[:APPLIES_TO]-(sec:Section)
            RETURN sec.chunk_id AS chunk_id,
                   sec.title    AS title,
                   sec.doc_id   AS doc_id,
                   sec.pagerank AS importance
            ORDER BY coalesce(sec.pagerank, 0) DESC
            LIMIT 20
            """,
            barcode=barcode,
        )
        sections = [dict(r) for r in result]

    if not sections:
        # Fallback: full-text search on barcode
        result2 = driver.session().run(
            """
            MATCH (sec:Section)
            WHERE toLower(sec.content) CONTAINS toLower($barcode)
               OR sec.doc_id CONTAINS $barcode
            RETURN sec.chunk_id AS chunk_id, sec.title AS title, sec.doc_id AS doc_id
            LIMIT 10
            """,
            barcode=barcode,
        )
        sections = [dict(r) for r in result2]

    return {"barcode": barcode, "sections": sections, "count": len(sections)}


@router.get("/steps/{chunk_id}")
async def ar_steps(
    chunk_id: str,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return ordered work steps, tools, materials, and safety warnings
    for the given section — formatted for AR overlay display.
    """
    driver = get_driver()
    with driver.session() as s:
        steps_r = s.run(
            """
            MATCH (sec:Section {chunk_id: $cid})-[:HAS_STEP]->(step:Step)
            RETURN step.step_id AS step_id, step.description AS description,
                   step.order AS order, step.duration_min AS duration_min
            ORDER BY step.order
            LIMIT 50
            """,
            cid=chunk_id,
        )
        steps = [dict(r) for r in steps_r]

        tools_r = s.run(
            """
            MATCH (sec:Section {chunk_id: $cid})-[:REQUIRES_TOOL]->(t:Tool)
            RETURN t.name AS name, t.tool_id AS tool_id, t.specification AS spec
            LIMIT 20
            """,
            cid=chunk_id,
        )
        tools = [dict(r) for r in tools_r]

        constraints_r = s.run(
            """
            MATCH (sec:Section {chunk_id: $cid})-[:HAS_CONSTRAINT]->(c:Constraint)
            RETURN c.parameter AS parameter, c.value AS value, c.unit AS unit
            LIMIT 10
            """,
            cid=chunk_id,
        )
        constraints = [dict(r) for r in constraints_r]

    # If no Step nodes yet, derive pseudo-steps from section content
    if not steps:
        steps = [{"step_id": "auto", "description": "请参考对应工艺章节内容", "order": 1}]

    return {
        "chunk_id":    chunk_id,
        "steps":       steps,
        "tools":       tools,
        "constraints": constraints,
    }


@router.post("/step-complete")
async def ar_step_complete(
    body: StepCompleteRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Record that an operator has completed a work step.

    1. Writes a StepCompletion node to Neo4j.
    2. If MES_WEBHOOK_URL is configured, POSTs completion event to MES.
    """
    driver = get_driver()
    with driver.session() as s:
        s.run(
            """
            MERGE (sc:StepCompletion {
                chunk_id: $chunk_id, step_order: $step_order,
                work_order_id: $wo_id
            })
            SET sc.operator_id  = $op_id,
                sc.completed_at = datetime(),
                sc.notes        = $notes
            """,
            chunk_id=body.chunk_id,
            step_order=body.step_order,
            wo_id=body.work_order_id,
            op_id=body.operator_id or str(user.id),
            notes=body.notes,
        )

    # MES webhook
    if MES_WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(MES_WEBHOOK_URL, json={
                    "event":         "step_completed",
                    "work_order_id": body.work_order_id,
                    "chunk_id":      body.chunk_id,
                    "step_order":    body.step_order,
                    "operator_id":   body.operator_id or str(user.id),
                    "notes":         body.notes,
                })
        except Exception as exc:
            log.warning("MES webhook failed: %s", exc)

    return {"ok": True, "chunk_id": body.chunk_id, "step_order": body.step_order}


@router.get("/overlay/{chunk_id}")
async def ar_overlay(
    chunk_id: str,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Complete AR overlay payload: steps + tools + constraints + hazard warnings.
    Optimised for single-fetch by AR clients.
    """
    steps_data = await ar_steps(chunk_id, _)
    driver = get_driver()
    with driver.session() as s:
        hazards_r = s.run(
            """
            MATCH (sec:Section {chunk_id: $cid})-[:WARNS_OF]->(h:Hazard)
            RETURN h.name AS name, h.severity AS severity, h.description AS description
            LIMIT 10
            """,
            cid=chunk_id,
        )
        hazards = [dict(r) for r in hazards_r]

    return {**steps_data, "hazards": hazards}
