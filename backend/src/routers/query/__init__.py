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
    req:          QueryRequest,
    current_user: User = Depends(get_current_user),
    driver:       Driver = Depends(get_protected_driver),
    db:           AsyncSession = Depends(get_db),
):
    return await query_sync(request, req, driver, current_user, db)


@router.post("/query/stream")
@limiter.limit("30/minute")
async def query_stream_route(
    request:      Request,
    req:          QueryRequest,
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

    with driver.session() as session:
        sec_result = session.run("""
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})
            RETURN s.chunk_id AS id, s.title AS name,
                   s.doc_id AS doc_id, s.number AS number
        """, ids=ids)
        nodes = []
        seen_ids: set[str] = set()
        for r in sec_result:
            cid = r["id"]
            nodes.append({
                "id": cid, "name": r["name"] or cid, "type": "Section",
                "doc_id": r["doc_id"] or "", "number": r["number"] or "",
                "rank": rank_map.get(cid, 0),
            })
            seen_ids.add(cid)

        doc_result = session.run("""
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})<-[:HAS_SECTION]-(d:Document)
            RETURN DISTINCT d.name AS id, coalesce(d.title, d.name) AS name, d.name AS doc_id
        """, ids=ids)
        for r in doc_result:
            if r["id"] not in seen_ids:
                nodes.append({"id": r["id"], "name": r["name"], "type": "Document",
                               "doc_id": r["doc_id"], "rank": 0})
                seen_ids.add(r["id"])

        entity_result = session.run("""
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})-[r]->(e)
            WHERE e:Tool OR e:Material OR e:Process OR e:Constraint
            RETURN DISTINCT
                coalesce(e.name, e.constraint_id) AS id,
                coalesce(e.name, e.type + ': ' + e.value + e.unit) AS name,
                labels(e)[0] AS type,
                coalesce(e.doc_id, '') AS doc_id
            LIMIT 40
        """, ids=ids)
        for r in entity_result:
            eid = r["id"]
            if eid and eid not in seen_ids:
                nodes.append({"id": eid, "name": r["name"] or eid,
                               "type": r["type"], "doc_id": r["doc_id"], "rank": 0})
                seen_ids.add(eid)

        neighbor_result = session.run("""
            UNWIND $ids AS cid
            MATCH (s:Section {chunk_id: cid})-[:HAS_SUBSECTION|NEXT_SECTION]->(nb:Section)
            WHERE NOT nb.chunk_id IN $ids
            RETURN DISTINCT nb.chunk_id AS id, nb.title AS name,
                            nb.doc_id AS doc_id, nb.number AS number
            LIMIT 20
        """, ids=ids)
        for r in neighbor_result:
            nid = r["id"]
            if nid not in seen_ids:
                nodes.append({"id": nid, "name": r["name"] or nid, "type": "Section",
                               "doc_id": r["doc_id"] or "", "number": r["number"] or "", "rank": 0})
                seen_ids.add(nid)

        edges = []
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
        sec_result = session.run("""
            MATCH (s:Section)
            WHERE toLower(s.title)   CONTAINS toLower($q)
               OR toLower(s.content) CONTAINS toLower($q)
            RETURN DISTINCT s.title AS text, 'section' AS type, s.doc_id AS doc_id
            LIMIT 5
        """, q=q)
        for r in sec_result:
            if r["text"]:
                suggestions.append({"text": r["text"], "type": r["type"], "doc_id": r["doc_id"] or ""})

        entity_result = session.run("""
            MATCH (e)
            WHERE (e:Tool OR e:Material OR e:Process)
              AND toLower(e.name) CONTAINS toLower($q)
            RETURN DISTINCT e.name AS text, labels(e)[0] AS type, e.doc_id AS doc_id
            LIMIT 5
        """, q=q)
        for r in entity_result:
            if r["text"]:
                suggestions.append({"text": r["text"], "type": r["type"].lower(), "doc_id": r["doc_id"] or ""})

    return {"suggestions": suggestions[:10]}


@router.post("/query/compare")
@limiter.limit("10/minute")
async def query_compare_route(
    request: Request,
    req:     QueryRequest,
    current_user: User = Depends(get_current_user),
    driver:  Driver     = Depends(get_protected_driver),
    db:      AsyncSession = Depends(get_db),
):
    return await query_compare(req, driver, current_user, db)


@router.post("/query/auto-strategy")
async def auto_strategy(req: QueryRequest):
    """
    根据问题类型自动推荐检索策略。
    对比型 → parallel，步骤/流程型 → graph_augmented，
    约束参数型 → graph_augmented，跨引用型 → multi_hop，其他 → parallel
    """
    q = req.question.lower()

    if any(kw in q for kw in ["对比", "比较", "区别", "不同", "差异"]):
        strategy, reason = "parallel", "对比型问题适合并行全文+向量检索"
    elif any(kw in q for kw in ["引用", "参照", "规范要求", "另一"]):
        strategy, reason = "multi_hop", "跨文档引用问题适合多跳推理"
    elif any(kw in q for kw in ["力矩", "温度", "压力", "公差", "参数", "数值", "范围", "极限"]):
        strategy, reason = "graph_augmented", "工艺约束参数问题适合图谱增强检索"
    elif any(kw in q for kw in ["如何", "步骤", "流程", "怎么", "操作", "程序", "顺序"]):
        strategy, reason = "graph_augmented", "步骤/流程型问题适合图谱增强检索"
    else:
        strategy, reason = "parallel", "通用问题使用并行检索"

    return {"strategy": strategy, "reason": reason, "question": req.question}
