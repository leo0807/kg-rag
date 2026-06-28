"""
Supply-chain knowledge graph: suppliers, BOM, CAD metadata.

GET  /api/graph/suppliers           — 查询材料对应的合格供应商
POST /api/admin/graph/suppliers/import — 批量导入供应商数据
POST /api/admin/graph/bom/import   — 从 ERP/PDM 导入 BOM 数据
GET  /api/graph/bom                — 按零件号查询 BOM 层级
POST /api/admin/graph/cad/ingest   — 导入 STEP/IGES 几何元数据
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel

from ...auth.deps import get_admin_user, get_current_user
from ...core.database import get_driver
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(tags=["supply-chain"])


# ---------------------------------------------------------------------------
# Supplier graph
# ---------------------------------------------------------------------------

def _query_suppliers(material: str | None, approval_status: str | None) -> list[dict]:
    driver = get_driver()
    with driver.session() as s:
        where_parts = []
        params: dict[str, Any] = {}
        if material:
            where_parts.append("(m.name CONTAINS $mat OR m.material_id = $mat)")
            params["mat"] = material
        if approval_status:
            where_parts.append("sup.approval_status = $status")
            params["status"] = approval_status
        where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
        result = s.run(
            f"""
            MATCH (m:Material)-[:SUPPLIED_BY]->(sup:Supplier)
            {where_clause}
            RETURN m.name AS material, m.material_id AS material_id,
                   sup.supplier_id AS supplier_id, sup.name AS supplier_name,
                   sup.approval_status AS approval_status,
                   sup.lead_time AS lead_time, sup.country AS country
            ORDER BY sup.approval_status, sup.name
            LIMIT 100
            """, **params,
        )
        return [dict(r) for r in result]


@router.get("/api/graph/suppliers")
async def get_suppliers(
    material: str | None = Query(None, description="材料名称或 ID"),
    approval_status: str | None = Query(None, description="approved | conditional | unapproved"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return approved suppliers for a material, with lead time and approval status."""
    rows = await asyncio.to_thread(_query_suppliers, material, approval_status)
    return {"count": len(rows), "material_filter": material, "suppliers": rows}


class SupplierImportBody(BaseModel):
    suppliers: list[dict]  # [{supplier_id, name, material_id, approval_status, lead_time}]


@router.post("/api/admin/graph/suppliers/import")
async def import_suppliers(
    body: SupplierImportBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Bulk-import supplier nodes and link to Material nodes."""
    driver = get_driver()
    created = 0
    with driver.session() as s:
        for sup in body.suppliers:
            sid = sup.get("supplier_id") or sup.get("name", "").replace(" ", "_")
            s.run("""
                MERGE (sup:Supplier {supplier_id: $sid})
                SET sup.name = $name,
                    sup.approval_status = $status,
                    sup.lead_time = $lead_time,
                    sup.country = $country
                WITH sup
                MATCH (m:Material)
                WHERE m.material_id = $mat OR m.name = $mat
                MERGE (m)-[:SUPPLIED_BY]->(sup)
            """, sid=sid, name=sup.get("name", sid),
               status=sup.get("approval_status", "unknown"),
               lead_time=sup.get("lead_time"),
               country=sup.get("country", ""),
               mat=sup.get("material_id", ""))
            created += 1
    return {"ok": True, "imported": created}


# ---------------------------------------------------------------------------
# BOM integration
# ---------------------------------------------------------------------------

class BOMImportBody(BaseModel):
    bom_entries: list[dict]  # [{part_no, parent_part_no, quantity, unit, source}]
    source: str = "ERP"


def _import_bom(entries: list[dict], source: str) -> int:
    driver = get_driver()
    n = 0
    with driver.session() as s:
        for entry in entries:
            pn     = entry.get("part_no", "")
            parent = entry.get("parent_part_no")
            if not pn:
                continue
            s.run("""
                MERGE (comp:Component {part_no: $pn})
                SET comp.bom_source = $src, comp.quantity = $qty, comp.unit = $unit
            """, pn=pn, src=source, qty=entry.get("quantity"), unit=entry.get("unit", "ea"))
            if parent:
                s.run("""
                    MATCH (child:Component {part_no: $child})
                    MERGE (parent:Component {part_no: $par})
                    MERGE (parent)-[:HAS_CHILD_COMPONENT]->(child)
                """, child=pn, par=parent)
            n += 1
    return n


@router.post("/api/admin/graph/bom/import")
async def import_bom(
    body: BOMImportBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Import Bill-of-Materials from ERP/PDM and link to Component nodes."""
    n = await asyncio.to_thread(_import_bom, body.bom_entries, body.source)
    return {"ok": True, "imported": n, "source": body.source}


@router.get("/api/graph/bom")
async def get_bom(
    part_no: str = Query(..., description="根零件编号"),
    depth:   int = Query(3, ge=1, le=6),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return BOM hierarchy for a part number (up to N levels deep)."""
    driver = get_driver()
    with driver.session() as s:
        result = s.run(f"""
            MATCH path = (root:Component {{part_no: $pn}})
                          -[:HAS_CHILD_COMPONENT*0..{depth}]->(child:Component)
            RETURN child.part_no AS part_no, length(path) AS level,
                   child.quantity AS quantity, child.unit AS unit
            ORDER BY level, part_no
            LIMIT 500
        """, pn=part_no)
        bom = [dict(r) for r in result]
    return {"root": part_no, "depth": depth, "item_count": len(bom), "bom": bom}


# ---------------------------------------------------------------------------
# CAD metadata ingestion
# ---------------------------------------------------------------------------

class CADMetaBody(BaseModel):
    part_no:      str
    file_format:  str = "STEP"     # STEP | IGES
    material:     str | None = None
    tolerance:    str | None = None  # e.g. "±0.05 mm"
    surface_finish: str | None = None
    weight_kg:    float | None = None
    constraints:  list[dict] = []   # [{parameter, value, unit}]


def _ingest_cad(meta: CADMetaBody) -> None:
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MERGE (comp:Component {part_no: $pn})
            SET comp.cad_format    = $fmt,
                comp.material      = $mat,
                comp.tolerance     = $tol,
                comp.surface_finish = $sf,
                comp.weight_kg     = $wt,
                comp.cad_ingested  = true
        """, pn=meta.part_no, fmt=meta.file_format,
            mat=meta.material, tol=meta.tolerance,
            sf=meta.surface_finish, wt=meta.weight_kg)
        for c in meta.constraints:
            s.run("""
                MATCH (comp:Component {part_no: $pn})
                MERGE (con:Constraint {parameter: $param, source: 'CAD'})
                SET con.value = $val, con.unit = $unit
                MERGE (comp)-[:HAS_CAD_CONSTRAINT]->(con)
            """, pn=meta.part_no, param=c.get("parameter", ""),
                val=str(c.get("value", "")), unit=c.get("unit", ""))


@router.post("/api/admin/graph/cad/ingest")
async def ingest_cad_metadata(
    body: CADMetaBody,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """
    Write STEP/IGES geometry metadata (material, tolerance, surface finish)
    to the Component node and link extracted Constraint nodes.
    """
    background_tasks.add_task(_ingest_cad, body)
    return {"ok": True, "part_no": body.part_no, "format": body.file_format, "status": "queued"}
