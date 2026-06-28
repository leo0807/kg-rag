"""
Knowledge collaboration — expert entry, review workflow, contribution ranking,
QA graph mounting.

POST /api/admin/knowledge/entry                  — 专家直接录入工艺知识条目
GET  /api/admin/knowledge/review-queue           — 待审核节点/关系队列
POST /api/admin/knowledge/review/{node_id}/approve
POST /api/admin/knowledge/review/{node_id}/reject
GET  /api/admin/knowledge/contributors           — 知识贡献排行
POST /api/query/attach-to-graph                  — 将用户问答节点挂载到图谱
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user, get_current_user
from ...core.database import get_driver
from ...db.models import AuditLog, User
from ...db.session import get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge-collab"])


# ---------------------------------------------------------------------------
# Expert knowledge entry
# ---------------------------------------------------------------------------

class KnowledgeEntry(BaseModel):
    entity_type:  str            # Tool | Process | Constraint | Material
    name:         str
    properties:   dict[str, Any] = {}
    doc_id:       str | None = None  # Link to source document if known


@router.post("/api/admin/knowledge/entry")
async def create_knowledge_entry(
    body:  KnowledgeEntry,
    admin: User = Depends(get_admin_user),
    db:    AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a new graph node in 'draft' state from expert input.
    A domain expert must approve it before it enters the search index.
    """
    node_id = str(uuid.uuid4())[:12]
    driver  = get_driver()
    with driver.session() as s:
        props = {**body.properties, "name": body.name, "status": "draft",
                 "created_by": str(admin.id), "node_id": node_id,
                 "created_at": datetime.now(timezone.utc).isoformat()}
        s.run(
            f"MERGE (n:{body.entity_type} {{node_id: $nid}}) "
            f"SET n += $props",
            nid=node_id, props=props,
        )
        if body.doc_id:
            s.run(
                "MATCH (n {node_id: $nid}), (doc:Document {doc_id: $did}) "
                "MERGE (doc)-[:HAS_ENTITY]->(n)",
                nid=node_id, did=body.doc_id,
            )
    db.add(AuditLog(user_id=str(admin.id), action="knowledge.entry.create",
                    resource_type=body.entity_type, detail={"node_id": node_id, "name": body.name}))
    await db.commit()
    return {"ok": True, "node_id": node_id, "status": "draft"}


# ---------------------------------------------------------------------------
# Review workflow
# ---------------------------------------------------------------------------

@router.get("/api/admin/knowledge/review-queue")
async def review_queue(
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Return nodes in 'draft' state awaiting expert approval."""
    driver = get_driver()
    with driver.session() as s:
        label = entity_type or ""
        cypher = (
            f"MATCH (n:{label} {{status: 'draft'}}) " if label else
            "MATCH (n {status: 'draft'}) "
        )
        result = s.run(
            cypher + "RETURN n.node_id AS node_id, labels(n) AS labels, "
                     "n.name AS name, n.created_by AS created_by, "
                     "n.created_at AS created_at LIMIT $lim",
            lim=limit,
        )
        nodes = [dict(r) for r in result]
    return {"count": len(nodes), "nodes": nodes}


@router.post("/api/admin/knowledge/review/{node_id}/approve")
async def approve_node(
    node_id: str,
    admin: User = Depends(get_admin_user),
    db:    AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MATCH (n {node_id: $nid}) "
            "SET n.status = 'approved', n.approved_by = $uid, n.approved_at = $ts",
            nid=node_id, uid=str(admin.id),
            ts=datetime.now(timezone.utc).isoformat(),
        )
    db.add(AuditLog(user_id=str(admin.id), action="knowledge.review.approve",
                    resource_type="node", detail={"node_id": node_id}))
    await db.commit()
    return {"ok": True, "node_id": node_id, "status": "approved"}


@router.post("/api/admin/knowledge/review/{node_id}/reject")
async def reject_node(
    node_id: str,
    reason:  str = "",
    admin:   User = Depends(get_admin_user),
    db:      AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MATCH (n {node_id: $nid}) SET n.status = 'rejected', n.reject_reason = $r",
            nid=node_id, r=reason,
        )
    db.add(AuditLog(user_id=str(admin.id), action="knowledge.review.reject",
                    resource_type="node", detail={"node_id": node_id, "reason": reason}))
    await db.commit()
    return {"ok": True, "node_id": node_id, "status": "rejected"}


# ---------------------------------------------------------------------------
# Contribution ranking
# ---------------------------------------------------------------------------

@router.get("/api/admin/knowledge/contributors")
async def contributor_rankings(
    days: int = Query(30, ge=1, le=365),
    _:   User = Depends(get_admin_user),
    db:  AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return top contributors by approved entries and reviews."""
    from datetime import timedelta  # noqa: PLC0415
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await db.execute(text("""
        SELECT user_id,
               COUNT(*) FILTER (WHERE action = 'knowledge.entry.create')  AS entries,
               COUNT(*) FILTER (WHERE action = 'knowledge.review.approve') AS approvals,
               COUNT(*) FILTER (WHERE action = 'knowledge.review.reject')  AS rejections
        FROM audit_logs
        WHERE action LIKE 'knowledge.%'
          AND created_at >= :since
        GROUP BY user_id
        ORDER BY (entries + approvals) DESC
        LIMIT 20
    """), {"since": since})
    contributors = [
        {
            "user_id":   r[0],
            "entries":   r[1],
            "approvals": r[2],
            "rejections": r[3],
            "score":     r[1] + r[2] * 2,
        }
        for r in rows
    ]
    return {"period_days": days, "count": len(contributors), "contributors": contributors}


# ---------------------------------------------------------------------------
# QA graph mounting
# ---------------------------------------------------------------------------

class AttachQueryBody(BaseModel):
    question:    str
    answer:      str
    chunk_ids:   list[str]   # Section nodes that answered the question
    session_id:  str | None = None


@router.post("/api/query/attach-to-graph")
async def attach_query_to_graph(
    body: AttachQueryBody,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Mount a user Q&A as a Query node connected to answering Section nodes.
    High-frequency question sections get automatic weight boost.
    """
    qid    = str(uuid.uuid4())[:12]
    driver = get_driver()
    with driver.session() as s:
        s.run(
            "MERGE (q:Query {query_id: $qid}) "
            "SET q.question = $question, q.answer = $answer, "
            "    q.user_id = $uid, q.created_at = $ts",
            qid=qid, question=body.question, answer=body.answer,
            uid=str(user.id), ts=datetime.now(timezone.utc).isoformat(),
        )
        for chunk_id in body.chunk_ids:
            s.run(
                "MATCH (q:Query {query_id: $qid}), (s:Section {chunk_id: $cid}) "
                "MERGE (q)-[:ANSWERED_BY]->(s) "
                "SET s.query_count = coalesce(s.query_count, 0) + 1",
                qid=qid, cid=chunk_id,
            )
    return {"ok": True, "query_id": qid, "sections_linked": len(body.chunk_ids)}
