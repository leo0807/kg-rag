import asyncio
import json
import logging
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from neo4j import Driver
from pydantic import BaseModel

from ..core.config import settings
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


# ── 导览讲解：流式LLM调用 ──────────────────────────────────────────────────────
async def _stream_explanation(topic: str, node: dict) -> AsyncIterator[str]:
    """为导览节点生成流式 AI 讲解（调用 OpenAI-compatible API）。"""
    type_label = {
        "Section":    "章节",
        "Document":   "文档",
        "Tool":       "工具/设备",
        "Material":   "材料",
        "Process":    "工艺工序",
        "Constraint": "技术约束",
        "Image":      "图表",
    }.get(node.get("type", ""), node.get("type", ""))

    name    = node.get("name") or node.get("id", "")
    content = (node.get("content") or node.get("description") or "")[:400]
    doc_id  = node.get("doc_id", "")

    user_prompt = (
        f"导览主题：「{topic}」\n"
        f"当前节点（{type_label}）：{name}"
        + (f"\n所属文档：{doc_id}" if doc_id else "")
        + (f"\n内容摘要：{content}" if content else "")
        + f"\n\n请用2~3句话介绍该{type_label}在「{topic}」中的作用与重要性，"
          f"语言简洁专业，适合航空工程师快速理解。"
    )

    payload = {
        "model":       settings.LLM_MODEL,
        "messages":    [
            {"role": "system", "content":
                "你是航空工艺规范知识库的AI导览员，用简洁专业的语言讲解每个节点的知识要点。"},
            {"role": "user",   "content": user_prompt},
        ],
        "stream":      True,
        "max_tokens":  180,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            async with client.stream(
                "POST",
                f"{settings.LLM_API_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("导览LLM调用失败: %s", exc)
        # 降级：返回节点摘要
        fallback = f"（{name}：{content[:80]}{'…' if len(content) > 80 else ''}）"
        yield fallback


@router.get("/graph/hot-nodes")
async def graph_hot_nodes(days: int = 30, top_k: int = 200):
    """
    返回热点 Section 节点的归一化热力值，供图谱可视化使用（无需鉴权）。
    热力值 = cited_count + clicked_count × 3，归一化到 [0, 1]。
    """
    import json as _json
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from ..routers.feedback import QueryFeedback
    from ..db.session import AsyncSessionLocal

    since = datetime.utcnow() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(QueryFeedback.sources, QueryFeedback.detail)
            .where(QueryFeedback.created_at >= since)
        )
        rows = result.all()

    cited:   dict[str, int] = {}
    clicked: dict[str, int] = {}

    for sources_json, detail in rows:
        try:
            for s in _json.loads(sources_json or "[]"):
                cid = s.get("chunk_id")
                if cid:
                    cited[cid] = cited.get(cid, 0) + 1
        except Exception:
            pass
        if detail and detail.startswith("clicked_source:"):
            cid = detail[len("clicked_source:"):]
            if cid:
                clicked[cid] = clicked.get(cid, 0) + 1

    all_ids = set(cited) | set(clicked)
    if not all_ids:
        return {"nodes": [], "max_heat": 0}

    heat = {cid: cited.get(cid, 0) + clicked.get(cid, 0) * 3.0 for cid in all_ids}
    max_heat = max(heat.values())
    ranked   = sorted(all_ids, key=lambda k: heat[k], reverse=True)[:top_k]

    return {
        "nodes": [
            {"chunk_id": cid, "heat_score": heat[cid], "heat_norm": round(heat[cid] / max_heat, 4)}
            for cid in ranked
        ],
        "max_heat": max_heat,
    }


@router.get("/graph")
async def get_graph(
    limit_doc:    int = 50,
    limit_sec:    int = 200,
    limit_img:    int = 100,
    limit_entity: int = 100,
    doc_id:       str = "",       # 按文档 doc_id 筛选
    driver: Driver = Depends(get_driver),
):
    with driver.session() as session:
        doc_filter = "WHERE $doc_id = '' OR d.name = $doc_id" if doc_id else ""

        # ── Document 节点 ─────────────────────────────────────────────────────
        doc_result = session.run(f"""
            MATCH (d:Document)
            {("WHERE $doc_id = '' OR d.name = $doc_id") if True else ""}
            RETURN d.name AS id, coalesce(d.title, d.name) AS name,
                   d.name AS doc_id, d.version AS version, 'Document' AS type
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_doc)
        nodes = [
            {
                "id":      r["id"],
                "name":    r["name"],
                "doc_id":  r["doc_id"],
                "version": r["version"] or "",
                "type":    "Document",
            }
            for r in doc_result
        ]

        # ── Section 节点 ──────────────────────────────────────────────────────
        sec_result = session.run("""
            MATCH (s:Section)
            WHERE $doc_id = '' OR s.doc_id = $doc_id
            RETURN s.chunk_id AS id, s.title AS name, s.doc_id AS doc_id, 'Section' AS type
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_sec)
        nodes += [
            {"id": r["id"], "name": r["name"] or r["id"], "type": "Section", "doc_id": r["doc_id"]}
            for r in sec_result
        ]

        # ── Image 节点 ────────────────────────────────────────────────────────
        img_result = session.run("""
            MATCH (i:Image)
            WHERE $doc_id = '' OR i.doc_id = $doc_id
            RETURN i.image_id AS id, i.caption AS name,
                   i.doc_id AS doc_id, i.description AS description, i.path AS path
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_img)
        nodes += [
            {
                "id":          r["id"],
                "name":        r["name"] or r["id"],
                "type":        "Image",
                "doc_id":      r["doc_id"],
                "description": r["description"] or "",
                "path":        r["path"] or "",
            }
            for r in img_result
        ]

        # ── Tool 节点 ─────────────────────────────────────────────────────────
        tool_result = session.run("""
            MATCH (t:Tool)
            WHERE $doc_id = '' OR t.doc_id = $doc_id
            RETURN t.name AS id, t.name AS name, t.doc_id AS doc_id, 'Tool' AS type
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_entity)
        nodes += [
            {"id": r["id"], "name": r["name"], "type": "Tool", "doc_id": r["doc_id"] or ""}
            for r in tool_result
        ]

        # ── Material 节点 ─────────────────────────────────────────────────────
        mat_result = session.run("""
            MATCH (m:Material)
            RETURN m.name AS id, m.name AS name, m.doc_id AS doc_id, 'Material' AS type
            LIMIT 100
        """)
        nodes += [
            {"id": r["id"], "name": r["name"], "type": "Material", "doc_id": r["doc_id"] or ""}
            for r in mat_result
        ]

        # ── Process 节点 ──────────────────────────────────────────────────────
        proc_result = session.run("""
            MATCH (p:Process)
            RETURN p.name AS id, p.name AS name, p.doc_id AS doc_id, 'Process' AS type
            LIMIT 100
        """)
        nodes += [
            {"id": r["id"], "name": r["name"], "type": "Process", "doc_id": r["doc_id"] or ""}
            for r in proc_result
        ]

        # ── Constraint 节点 ───────────────────────────────────────────────────
        con_result = session.run("""
            MATCH (c:Constraint)
            RETURN c.constraint_id AS id,
                   c.type + ': ' + c.value + c.unit AS name,
                   c.type AS con_type, c.value AS value, c.value_max AS value_max,
                   c.unit AS unit, c.description AS description,
                   c.standard AS standard, c.doc_id AS doc_id
            LIMIT 200
        """)
        nodes += [
            {
                "id":          r["id"],
                "name":        r["name"],
                "type":        "Constraint",
                "con_type":    r["con_type"],
                "value":       r["value"],
                "value_max":   r["value_max"] or "",
                "unit":        r["unit"],
                "description": r["description"] or "",
                "standard":    r["standard"] or "",
                "doc_id":      r["doc_id"] or "",
            }
            for r in con_result
        ]

        node_ids = {n["id"] for n in nodes}

        # ── 关系 ──────────────────────────────────────────────────────────────
        edges = []

        def _query_edges(cypher: str, **params):
            result = session.run(cypher, **params)
            return [
                dict(r) for r in result
                if r["source"] in node_ids and r["target"] in node_ids
            ]

        edges += _query_edges("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
            RETURN d.name AS source, s.chunk_id AS target, 'HAS_SECTION' AS type
            LIMIT 300
        """)
        edges += _query_edges("""
            MATCH (d:Document)-[:REFERENCES]->(r:Document)
            RETURN d.name AS source, r.name AS target, 'REFERENCES' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:HAS_SUBSECTION]->(c:Section)
            RETURN s.chunk_id AS source, c.chunk_id AS target, 'HAS_SUBSECTION' AS type
            LIMIT 300
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:HAS_IMAGE]->(i:Image)
            RETURN s.chunk_id AS source, i.image_id AS target, 'HAS_IMAGE' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:REQUIRES_TOOL]->(t:Tool)
            RETURN s.chunk_id AS source, t.name AS target, 'REQUIRES_TOOL' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:USES_MATERIAL]->(m:Material)
            RETURN s.chunk_id AS source, m.name AS target, 'USES_MATERIAL' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:INVOLVES_PROCESS]->(p:Process)
            RETURN s.chunk_id AS source, p.name AS target, 'INVOLVES_PROCESS' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:HAS_CONSTRAINT]->(c:Constraint)
            RETURN s.chunk_id AS source, c.constraint_id AS target, 'HAS_CONSTRAINT' AS type
            LIMIT 300
        """)
        edges += _query_edges("""
            MATCH (p:Process)-[:REQUIRES_TOOL]->(t:Tool)
            RETURN p.name AS source, t.name AS target, 'REQUIRES_TOOL' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (p:Process)-[:USES_MATERIAL]->(m:Material)
            RETURN p.name AS source, m.name AS target, 'USES_MATERIAL' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (a:Material)-[:ALTERNATIVE_TO]->(b:Material)
            RETURN a.name AS source, b.name AS target, 'ALTERNATIVE_TO' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (a)-[:COMPATIBLE_WITH]->(b)
            RETURN elementId(a) AS source_eid, a.name AS source,
                   elementId(b) AS target_eid, b.name AS target, 'COMPATIBLE_WITH' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (i:Image)-[:MENTIONS_TOOL]->(t:Tool)
            RETURN i.image_id AS source, t.name AS target, 'MENTIONS_TOOL' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (new_doc:Document)-[:SUPERSEDES]->(old_doc:Document)
            RETURN new_doc.name AS source, old_doc.name AS target, 'SUPERSEDES' AS type
            LIMIT 50
        """)
        edges += _query_edges("""
            MATCH (a:Section)-[r:SIMILAR_TO]-(b:Section)
            WHERE a.chunk_id < b.chunk_id
            RETURN a.chunk_id AS source, b.chunk_id AS target,
                   'SIMILAR_TO' AS type
            LIMIT 100
        """)

    return {"nodes": nodes, "edges": edges}


@router.get("/stats/knowledge-graph")
async def knowledge_graph_stats(driver: Driver = Depends(get_driver)):
    """
    返回知识图谱统计信息：各类节点数量、关系数量、覆盖率。
    """
    with driver.session() as session:

        # 节点计数
        node_counts = {}
        for label in ["Document", "Section", "Image", "Tool", "Material", "Process", "Constraint"]:
            r = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt").single()
            node_counts[label] = r["cnt"] if r else 0

        # 关系计数
        rel_counts = {}
        for rel in [
            "HAS_SECTION", "HAS_SUBSECTION", "NEXT_SECTION", "REFERENCES",
            "HAS_IMAGE", "REQUIRES_TOOL", "USES_MATERIAL", "INVOLVES_PROCESS",
            "HAS_CONSTRAINT", "ALTERNATIVE_TO", "COMPATIBLE_WITH",
            "MENTIONS_TOOL", "SUPERSEDES", "OBSOLETED_BY",
            "ADDED_SECTION", "REMOVED_SECTION", "CHANGED_TO", "SIMILAR_TO",
        ]:
            r = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt").single()
            rel_counts[rel] = r["cnt"] if r else 0

        # 覆盖率
        total_sections = node_counts["Section"] or 1
        r_tool = session.run("""
            MATCH (s:Section)-[:REQUIRES_TOOL]->(:Tool)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_mat = session.run("""
            MATCH (s:Section)-[:USES_MATERIAL]->(:Material)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_proc = session.run("""
            MATCH (s:Section)-[:INVOLVES_PROCESS]->(:Process)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_con = session.run("""
            MATCH (s:Section)-[:HAS_CONSTRAINT]->(:Constraint)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_img = session.run("""
            MATCH (s:Section)-[:HAS_IMAGE]->(:Image)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_sim = session.run("""
            MATCH (s:Section)-[:SIMILAR_TO]-()
            RETURN count(DISTINCT s) AS cnt
        """).single()

        coverage = {
            "sections_with_tool":       round((r_tool["cnt"]  if r_tool  else 0) / total_sections * 100, 1),
            "sections_with_material":   round((r_mat["cnt"]   if r_mat   else 0) / total_sections * 100, 1),
            "sections_with_process":    round((r_proc["cnt"]  if r_proc  else 0) / total_sections * 100, 1),
            "sections_with_constraint": round((r_con["cnt"]   if r_con   else 0) / total_sections * 100, 1),
            "sections_with_image":      round((r_img["cnt"]   if r_img   else 0) / total_sections * 100, 1),
            "sections_with_similar":    round((r_sim["cnt"]   if r_sim   else 0) / total_sections * 100, 1),
        }

    return {
        "nodes":    node_counts,
        "relations": rel_counts,
        "coverage": coverage,
        "total_nodes": sum(node_counts.values()),
        "total_relations": sum(rel_counts.values()),
    }


@router.get("/graph/timeline")
async def get_timeline(driver: Driver = Depends(get_driver)):
    """
    版本时间线数据：返回所有文档的版本信息与章节变更统计。
    X 轴 = 版本号（字母序），Y 轴 = 文档基名，气泡大小 = 变更量。
    """
    with driver.session() as session:
        # ① 所有已入库文档（有 title 的才算正式文档）
        docs_res = session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   COALESCE(d.version, '')    AS version,
                   COALESCE(d.issue_date, '') AS issue_date
            ORDER BY d.name
        """)
        docs: dict[str, dict] = {}
        for r in docs_res:
            docs[r["doc_id"]] = {
                "doc_id":           r["doc_id"],
                "title":            r["title"],
                "version":          r["version"],
                "issue_date":       r["issue_date"],
                "supersedes":       [],
                "added_sections":   0,
                "removed_sections": 0,
                "changed_sections": 0,
            }

        # ② 版本溯源关系 SUPERSEDES
        sup_res = session.run("""
            MATCH (new:Document)-[:SUPERSEDES]->(old:Document)
            RETURN new.name AS new_id, old.name AS old_id
        """)
        for r in sup_res:
            if r["new_id"] in docs:
                docs[r["new_id"]]["supersedes"].append(r["old_id"])

        # ③ 新增章节计数（ADDED_SECTION）
        added_res = session.run("""
            MATCH (d:Document)-[:ADDED_SECTION]->()
            RETURN d.name AS doc_id, count(*) AS cnt
        """)
        for r in added_res:
            if r["doc_id"] in docs:
                docs[r["doc_id"]]["added_sections"] = r["cnt"]

        # ④ 删除章节计数（REMOVED_SECTION）
        removed_res = session.run("""
            MATCH (d:Document)-[:REMOVED_SECTION]->()
            RETURN d.name AS doc_id, count(*) AS cnt
        """)
        for r in removed_res:
            if r["doc_id"] in docs:
                docs[r["doc_id"]]["removed_sections"] = r["cnt"]

        # ⑤ 内容变更章节计数（CHANGED_TO）
        changed_res = session.run("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:CHANGED_TO]->()
            RETURN d.name AS doc_id, count(s) AS cnt
        """)
        for r in changed_res:
            if r["doc_id"] in docs:
                docs[r["doc_id"]]["changed_sections"] = r["cnt"]

    return {"docs": list(docs.values())}


class TourRequest(BaseModel):
    topic:     str
    max_stops: int = 6


@router.post("/graph/tour")
async def graph_tour(
    req:    TourRequest,
    driver: Driver = Depends(get_driver),
):
    """
    图谱漫游：以主题为起点，AI 自动规划导览路径，流式讲解每个节点知识要点。

    SSE 事件格式：
      {"type":"init",  "total":N, "topic":"..."}
      {"type":"path",  "nodes":[...], "edges":[...]}   ← 导览子图
      {"type":"stop",  "index":i, "node_id":"...", "node":{...}}
      {"type":"delta", "content":"..."}                ← 流式AI讲解
      {"type":"next_stop"}                             ← 当前站讲解完毕
      {"type":"done"}
    """
    async def generate():
        # ── ① 检索与主题相关的章节 ──────────────────────────────────────────
        from .query.core import do_retrieval

        loop = asyncio.get_running_loop()
        try:
            sections, _ = await loop.run_in_executor(
                None,
                lambda: do_retrieval(driver, req.topic, "graph_augmented", top_k=10),
            )
        except Exception as exc:
            logger.warning("导览检索失败: %s", exc)
            sections = []

        if not sections:
            yield f'data: {json.dumps({"type":"error","message":"未找到与该主题相关的内容"}, ensure_ascii=False)}\n\n'
            return

        # ── ② 展开子图：章节 → 文档 + 实体邻居 ─────────────────────────────
        tour_nodes: list[dict] = []
        tour_edges: list[dict] = []
        seen_ids:   set[str]   = set()
        chunk_ids = [s["chunk_id"] for s in sections[: req.max_stops + 4]]

        def _add_node(n: dict) -> bool:
            if n["id"] in seen_ids:
                return False
            seen_ids.add(n["id"])
            tour_nodes.append(n)
            return True

        with driver.session() as session:
            rows = session.run("""
                UNWIND $chunk_ids AS cid
                MATCH (s:Section {chunk_id: cid})
                OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(s)
                OPTIONAL MATCH (s)-[:REQUIRES_TOOL]->(t:Tool)
                OPTIONAL MATCH (s)-[:USES_MATERIAL]->(m:Material)
                OPTIONAL MATCH (s)-[:INVOLVES_PROCESS]->(p:Process)
                RETURN
                    s.chunk_id                                   AS cid,
                    COALESCE(s.title, s.chunk_id)                AS sec_name,
                    s.doc_id                                     AS sec_doc,
                    COALESCE(s.content, '')                      AS sec_content,
                    d.name                                       AS doc_id,
                    COALESCE(d.title, d.name)                    AS doc_name,
                    collect(DISTINCT t.name)[0..2]               AS tools,
                    collect(DISTINCT m.name)[0..2]               AS mats,
                    collect(DISTINCT p.name)[0..2]               AS procs
            """, chunk_ids=chunk_ids)

            for row in rows:
                # Section node
                sec_node = {
                    "id":      row["cid"],
                    "name":    row["sec_name"],
                    "type":    "Section",
                    "doc_id":  row["sec_doc"] or "",
                    "content": (row["sec_content"] or "")[:300],
                    "label":   row["sec_name"],
                }
                _add_node(sec_node)

                # Document node
                if row["doc_id"]:
                    doc_node = {
                        "id":    row["doc_id"],
                        "name":  row["doc_name"],
                        "type":  "Document",
                        "doc_id": row["doc_id"],
                        "label": row["doc_name"],
                    }
                    if _add_node(doc_node):
                        tour_edges.append({"source": row["doc_id"], "target": row["cid"], "type": "HAS_SECTION"})

                # Entity nodes
                for names, etype, rel in [
                    (row["tools"], "Tool",     "REQUIRES_TOOL"),
                    (row["mats"],  "Material", "USES_MATERIAL"),
                    (row["procs"], "Process",  "INVOLVES_PROCESS"),
                ]:
                    for name in (names or []):
                        if not name:
                            continue
                        ent = {"id": name, "name": name, "type": etype, "label": name, "doc_id": ""}
                        if _add_node(ent):
                            tour_edges.append({"source": row["cid"], "target": name, "type": rel})

        # ── ③ 确定导览顺序：取前 max_stops 个章节节点 ─────────────────────
        stop_nodes = [
            n for n in tour_nodes
            if n["type"] == "Section" and n["id"] in {s["chunk_id"] for s in sections}
        ][: req.max_stops]

        if not stop_nodes:
            stop_nodes = [n for n in tour_nodes if n["type"] == "Section"][: req.max_stops]

        total = len(stop_nodes)

        # ── ④ 发送初始化帧 ─────────────────────────────────────────────────
        yield f'data: {json.dumps({"type":"init","total":total,"topic":req.topic}, ensure_ascii=False)}\n\n'
        yield f'data: {json.dumps({"type":"path","nodes":tour_nodes,"edges":tour_edges}, ensure_ascii=False)}\n\n'

        # ── ⑤ 逐站发送：stop → delta… → next_stop ──────────────────────
        for i, node in enumerate(stop_nodes):
            yield f'data: {json.dumps({"type":"stop","index":i,"node_id":node["id"],"node":node}, ensure_ascii=False)}\n\n'

            async for delta in _stream_explanation(req.topic, node):
                yield f'data: {json.dumps({"type":"delta","content":delta}, ensure_ascii=False)}\n\n'

            yield f'data: {json.dumps({"type":"next_stop"})}\n\n'

        yield f'data: {json.dumps({"type":"done"})}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/graph/semantic-links")
async def trigger_semantic_links(
    threshold: float = 0.88,
    top_k: int = 5,
    dry_run: bool = False,
    driver: Driver = Depends(get_driver),
):
    """
    触发跨文档语义边构建（离线批处理）。
    可先用 dry_run=true 预览会写入多少条边。
    """
    from ..services.semantic_linker import build_semantic_links
    result = build_semantic_links(driver, threshold=threshold, top_k=top_k, dry_run=dry_run)
    return result
