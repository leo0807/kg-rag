"""图谱节点/关系编辑 — 管理员专属，附审计日志"""
from __future__ import annotations
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from neo4j import Driver
from ..core.database import get_driver
from ..db.session import get_db
from ..db.models import User, AuditLog
from ..auth.deps import get_admin_user

router = APIRouter(prefix="/api/graph", tags=["graph-edit"])

# Keys that must not be modified via API
_READONLY_KEYS = {"chunk_id", "doc_id", "name", "id"}


class NodePatchRequest(BaseModel):
    properties: dict


class EdgeCreateRequest(BaseModel):
    from_id: str
    to_id: str
    rel_type: str
    properties: dict = {}


@router.patch("/nodes/{node_id}")
async def patch_node(
    node_id: str,
    req: NodePatchRequest,
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    safe = {k: v for k, v in req.properties.items() if k not in _READONLY_KEYS}
    if not safe:
        raise HTTPException(400, "没有可修改的属性")
    set_clause = ", ".join(f"n.`{k}` = ${k}" for k in safe)
    params = {"node_id": node_id, **safe}

    def _run():
        with driver.session() as s:
            rec = s.run(
                f"MATCH (n) WHERE n.chunk_id = $node_id OR n.name = $node_id "
                f"SET {set_clause} RETURN count(n) AS cnt",
                **params,
            ).single()
            return rec["cnt"] if rec else 0

    cnt = await asyncio.to_thread(_run)
    if cnt == 0:
        raise HTTPException(404, f"节点不存在: {node_id}")

    db.add(AuditLog(
        user_id=admin.id, action="node_patch", resource=node_id,
        detail=json.dumps(safe, ensure_ascii=False),
    ))
    await db.commit()
    return {"status": "OK", "updated": cnt}


@router.post("/edges")
async def create_edge(
    req: EdgeCreateRequest,
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    # Validate rel_type is a simple identifier
    if not req.rel_type.replace("_", "").isalnum():
        raise HTTPException(400, "关系类型只能包含字母、数字、下划线")
    props_clause = (" {" + ", ".join(f"`{k}`: ${k}" for k in req.properties) + "}") if req.properties else ""
    params = {"from_id": req.from_id, "to_id": req.to_id, **req.properties}

    def _run():
        with driver.session() as s:
            s.run(
                f"MATCH (a), (b) "
                f"WHERE (a.chunk_id = $from_id OR a.name = $from_id) "
                f"  AND (b.chunk_id = $to_id   OR b.name = $to_id) "
                f"CREATE (a)-[r:{req.rel_type}{props_clause}]->(b)",
                **params,
            )

    await asyncio.to_thread(_run)
    db.add(AuditLog(
        user_id=admin.id, action="edge_create",
        resource=f"{req.from_id}->{req.to_id}",
        detail=f"{req.rel_type} {json.dumps(req.properties, ensure_ascii=False)}",
    ))
    await db.commit()
    return {"status": "OK"}


@router.delete("/edges/{edge_id}")
async def delete_edge(
    edge_id: int,
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    def _run():
        with driver.session() as s:
            s.run("MATCH ()-[r]->() WHERE id(r) = $eid DELETE r", eid=edge_id)

    await asyncio.to_thread(_run)
    db.add(AuditLog(
        user_id=admin.id, action="edge_delete",
        resource=f"edge:{edge_id}", detail="",
    ))
    await db.commit()
    return {"status": "OK"}
