"""
src/routers/query/__init__.py
查询模块路由注册
"""
from fastapi import APIRouter, Depends, Request
from neo4j import Driver
from slowapi import Limiter
from slowapi.util import get_remote_address
from ...core.database import get_driver
from .models import QueryRequest, QueryResponse
from .sync   import query_sync
from .stream import query_stream

router  = APIRouter(prefix="/api", tags=["query"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver)):
    return await query_sync(request, req, driver)


@router.post("/query/stream")
@limiter.limit("30/minute")
async def query_stream_route(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver)):
    return await query_stream(request, req, driver)


@router.get("/query/source-graph")
async def source_graph(
    chunk_ids: str,          # 逗号分隔，顺序即优先级（第 1 个为最高相关）
    driver: Driver = Depends(get_driver),
):
    """
    返回一组 chunk_id 对应的知识图谱子图。
    nodes 带 rank 字段（1-based，0 表示非来源辅助节点）。
    """
    ids = [c.strip() for c in chunk_ids.split(",") if c.strip()]
    if not ids:
        return {"nodes": [], "edges": []}

    # rank 映射：chunk_id → 1-based 顺序
    rank_map = {cid: idx + 1 for idx, cid in enumerate(ids)}

    with driver.session() as session:
        # ── 1. 来源 Section 节点 ──────────────────────────────────────────────
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
                "id":     cid,
                "name":   r["name"] or cid,
                "type":   "Section",
                "doc_id": r["doc_id"] or "",
                "number": r["number"] or "",
                "rank":   rank_map.get(cid, 0),
            })
            seen_ids.add(cid)

        # ── 2. 父 Document 节点 ───────────────────────────────────────────────
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

        # ── 3. 直接关联的实体节点（Tool / Material / Process / Constraint）──────
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

        # ── 4. 来源章节间的邻居章节（HAS_SUBSECTION / NEXT_SECTION）──────────
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
                nodes.append({"id": nid, "name": r["name"] or nid,
                               "type": "Section", "doc_id": r["doc_id"] or "",
                               "number": r["number"] or "", "rank": 0})
                seen_ids.add(nid)

        # ── 5. 边 ──────────────────────────────────────────────────────────────
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