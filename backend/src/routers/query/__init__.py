"""
src/routers/query/__init__.py
查询模块路由注册
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from neo4j import Driver
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from ...core.database import get_driver
from ...auth import deps as auth_deps
from ...db.session import get_db
from ...db.models import User
from .models  import QueryRequest, QueryResponse
from ...services.qa.strategy_router import select_strategy
from .request_parser import parse_query_request
from .sync    import query_sync
from .stream  import query_stream
from .compare import query_compare

get_current_user = getattr(auth_deps, "get_current_user", getattr(auth_deps, "get_optional_user"))
get_protected_driver = getattr(auth_deps, "get_protected_driver", get_driver)

router  = APIRouter(prefix="/api", tags=["query"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query(
    request:      Request,
    req:          QueryRequest = Depends(parse_query_request),
    current_user: User = Depends(get_current_user),
    driver:       Driver = Depends(get_protected_driver),
    db:           AsyncSession = Depends(get_db),
):
    return await query_sync(request, req, driver, current_user, db)


@router.post("/query/stream")
@limiter.limit("30/minute")
async def query_stream_route(
    request:      Request,
    req:          QueryRequest = Depends(parse_query_request),
    current_user: User = Depends(get_current_user),
    driver:       Driver = Depends(get_protected_driver),
    db:           AsyncSession = Depends(get_db),
):
    return await query_stream(request, req, driver, current_user, db)


@router.get("/query/source-graph")
async def source_graph(
    chunk_ids: str,
    driver: Driver = Depends(get_driver),
):
    """
    返回一组 chunk_id 对应的知识图谱子图。
    nodes 带 rank 字段（1-based，0 表示非来源辅助节点）。
    """
    ids = [c.strip() for c in chunk_ids.split(",") if c.strip()]
    if not ids:
        return {"nodes": [], "edges": []}

    rank_map = {cid: idx + 1 for idx, cid in enumerate(ids)}

    nodes: list[dict] = []
    seen_ids: set[str] = set()

    with driver.session() as session:
        # 4 次串行查询合并为 1 次 UNION ALL，节省 3 次网络往返
        node_result = session.run("""
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})
            RETURN s.chunk_id AS id, coalesce(s.title, cid) AS name,
                   'Section' AS node_type,
                   coalesce(s.doc_id, '') AS doc_id, coalesce(s.number, '') AS number
            UNION ALL
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})<-[:HAS_SECTION]-(d:Document)
            RETURN DISTINCT d.name AS id, coalesce(d.title, d.name) AS name,
                   'Document' AS node_type, d.name AS doc_id, '' AS number
            UNION ALL
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})-[]->(e)
            WHERE (e:Tool OR e:Material OR e:Process OR e:Constraint)
            RETURN DISTINCT
                coalesce(e.name, e.constraint_id) AS id,
                coalesce(e.name, coalesce(e.constraint_id, '')) AS name,
                labels(e)[0] AS node_type,
                coalesce(e.doc_id, '') AS doc_id, '' AS number
            LIMIT 40
            UNION ALL
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})-[:HAS_SUBSECTION|NEXT_SECTION]->(nb:Section)
            WHERE NOT nb.chunk_id IN $ids
            RETURN DISTINCT nb.chunk_id AS id, coalesce(nb.title, nb.chunk_id) AS name,
                   'Section' AS node_type,
                   coalesce(nb.doc_id, '') AS doc_id, coalesce(nb.number, '') AS number
            LIMIT 20
        """, ids=ids)
        for r in node_result:
            nid = r["id"]
            if not nid or nid in seen_ids:
                continue
            node_type = r["node_type"]
            nodes.append({
                "id": nid, "name": r["name"] or nid, "type": node_type,
                "doc_id": r["doc_id"] or "", "number": r["number"] or "",
                "rank": rank_map.get(nid, 0) if node_type == "Section" else 0,
            })
            seen_ids.add(nid)

        edges: list[dict] = []
        edge_result = session.run("""
            MATCH (a)-[r]->(b)
            WHERE (a.chunk_id IN $seen OR a.name IN $seen OR a.constraint_id IN $seen)
              AND (b.chunk_id IN $seen OR b.name IN $seen OR b.constraint_id IN $seen)
            RETURN
                coalesce(a.chunk_id, a.name, a.constraint_id) AS source,
                coalesce(b.chunk_id, b.name, b.constraint_id) AS target,
                type(r) AS type
            LIMIT 200
        """, seen=list(seen_ids))
        for r in edge_result:
            src, tgt = r["source"], r["target"]
            if src in seen_ids and tgt in seen_ids and src != tgt:
                edges.append({"source": src, "target": tgt, "type": r["type"]})

    return {"nodes": nodes, "edges": edges}


@router.get("/query/suggest")
async def query_suggest(
    q:      str    = "",
    driver: Driver = Depends(get_driver),
):
    """基于知识图谱的查询建议/自动补全"""
    if not q.strip() or len(q) < 2:
        return {"suggestions": []}

    suggestions = []
    with driver.session() as session:
        # 2 次串行查询合并为 1 次 UNION ALL
        result = session.run("""
            MATCH (s:Section)
            WHERE toLower(s.title)   CONTAINS toLower($q)
               OR toLower(s.content) CONTAINS toLower($q)
            RETURN DISTINCT s.title AS text, 'section' AS type, coalesce(s.doc_id, '') AS doc_id
            LIMIT 5
            UNION ALL
            MATCH (e)
            WHERE (e:Tool OR e:Material OR e:Process)
              AND toLower(e.name) CONTAINS toLower($q)
            RETURN DISTINCT e.name AS text, toLower(labels(e)[0]) AS type, coalesce(e.doc_id, '') AS doc_id
            LIMIT 5
        """, q=q)
        for r in result:
            if r["text"]:
                suggestions.append({"text": r["text"], "type": r["type"], "doc_id": r["doc_id"]})

    return {"suggestions": suggestions[:10]}


@router.post("/query/compare")
@limiter.limit("10/minute")
async def query_compare_route(
    request: Request,
    req:     QueryRequest = Depends(parse_query_request),
    current_user: User = Depends(get_current_user),
    driver:  Driver     = Depends(get_protected_driver),
    db:      AsyncSession = Depends(get_db),
):
    return await query_compare(req, driver, current_user, db)


@router.post("/query/auto-strategy")
async def auto_strategy(req: QueryRequest):
    """推荐检索策略（不执行查询，保留向后兼容）。"""
    strategy, reason = select_strategy(req.question)
    return {"strategy": strategy, "reason": reason, "question": req.question}
