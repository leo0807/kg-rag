import logging

from fastapi import APIRouter, Depends, Query
from neo4j import Driver

from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


def _selected_ids(nodes: list[dict], node_type: str) -> list[str]:
    return [str(n["id"]) for n in nodes if n.get("type") == node_type and n.get("id")]


def _append_missing_owner_docs(nodes: list[dict]) -> list[dict]:
    """
    全局图下，如果先选中了图片/实体节点，但对应 Document 因 limit_doc 未被带出，
    前端会把这些节点显示成孤点。这里把缺失的宿主文档补回来，优先保证连通性。
    """
    existing_doc_ids = {str(n["id"]) for n in nodes if n.get("type") == "Document" and n.get("id")}
    extras: list[dict] = []

    for node in nodes:
        doc_id = str(node.get("doc_id") or "").strip()
        if not doc_id or doc_id in existing_doc_ids:
            continue
        extras.append({
            "id": doc_id,
            "name": doc_id,
            "doc_id": doc_id,
            "version": "",
            "type": "Document",
        })
        existing_doc_ids.add(doc_id)

    if extras:
        nodes.extend(extras)
    return nodes


@router.get("/graph/schema")
async def get_graph_schema(driver: Driver = Depends(get_driver)):
    """获取图谱 Schema，包括所有标签和关系类型"""
    with driver.session() as session:
        # 获取标签
        labels_result = session.run("CALL db.labels()")
        labels = [r[0] for r in labels_result]

        # 获取关系类型
        rel_types_result = session.run("CALL db.relationshipTypes()")
        rel_types = [r[0] for r in rel_types_result]

        # 获取更详细的 schema (可选，帮助前端连线约束)
        schema_result = session.run("CALL db.schema.visualization()")
        # 这里返回的是一个可视化图形，解析它比较复杂，我们可以先返回基础的 Labels 和 RelTypes
        
        return {
            "labels": labels,
            "relationship_types": rel_types
        }


@router.post("/graph/query")
async def execute_cypher_query(
    query: dict,
    driver: Driver = Depends(get_driver)
):
    """执行自定义 Cypher 查询并返回图结果"""
    cypher = query.get("cypher")
    if not cypher:
        return {"error": "Missing cypher query"}
    
    with driver.session() as session:
        try:
            result = session.run(cypher)
            nodes = []
            edges = []
            node_ids = set()

            for record in result:
                for key in record.keys():
                    val = record[key]
                    # 处理节点
                    if hasattr(val, "labels"):
                        try:
                            node_id = val.element_id
                        except AttributeError:
                            node_id = str(val.id)
                        
                        if node_id not in node_ids:
                            node_ids.add(node_id)
                            nodes.append({
                                "id": node_id,
                                "labels": list(val.labels),
                                "properties": dict(val.items()),
                                "type": list(val.labels)[0] if val.labels else "Unknown"
                            })
                    # 处理关系
                    elif hasattr(val, "type") and hasattr(val, "start_node"):
                        try:
                            rel_id = val.element_id
                            source_id = val.start_node.element_id
                            target_id = val.end_node.element_id
                        except AttributeError:
                            rel_id = str(val.id)
                            source_id = str(val.start_node.id)
                            target_id = str(val.end_node.id)

                        edges.append({
                            "id": rel_id,
                            "source": source_id,
                            "target": target_id,
                            "type": val.type,
                            "properties": dict(val.items())
                        })
            
            return {"nodes": nodes, "edges": edges, "success": True}
        except Exception as e:
            logger.error("Cypher execution failed: %s", e)
            return {"error": str(e), "success": False}


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
            select(QueryFeedback.sources)
            .where(QueryFeedback.created_at >= since)
        )
        rows = result.all()

    cited: dict[str, int] = {}

    for (sources_json,) in rows:
        try:
            for s in _json.loads(sources_json or "[]"):
                cid = s.get("chunk_id")
                if cid:
                    cited[cid] = cited.get(cid, 0) + 1
        except Exception:
            pass

    all_ids = set(cited)
    if not all_ids:
        return {"nodes": [], "max_heat": 0}

    heat = {cid: float(cited[cid]) for cid in all_ids}
    max_heat = max(heat.values())
    ranked   = sorted(all_ids, key=lambda k: heat[k], reverse=True)[:top_k]

    return {
        "nodes": [
            {"chunk_id": cid, "heat_score": heat[cid], "heat_norm": round(heat[cid] / max_heat, 4)}
            for cid in ranked
        ],
        "max_heat": max_heat,
    }


@router.get("/graph/expand/{chunk_id}")
async def expand_section(
    chunk_id: str,
    driver: Driver = Depends(get_driver),
):
    """返回指定 Section 的直接子节点（用于前端按需展开）"""
    with driver.session() as session:
        result = session.run("""
            MATCH (parent:Section {chunk_id: $chunk_id})-[:HAS_SUBSECTION]->(child:Section)
            OPTIONAL MATCH (child)-[:HAS_SUBSECTION]->(grandchild:Section)
            WITH child, count(grandchild) AS grandchildren_count
            RETURN child.chunk_id AS id,
                   child.title    AS name,
                   child.doc_id   AS doc_id,
                   child.level    AS level,
                   child.number   AS number,
                   grandchildren_count > 0 AS has_children,
                   'Section' AS type
        """, chunk_id=chunk_id)
        children = []
        for r in result:
            children.append({
                "id":           r["id"],
                "name":         r["name"] or r["id"],
                "type":         "Section",
                "doc_id":       r["doc_id"] or "",
                "level":        r["level"] or 1,
                "number":       r["number"] or "",
                "has_children": bool(r["has_children"]),
            })
    return {"nodes": children, "parent_id": chunk_id}


@router.get("/graph")
async def get_graph(
    limit_doc:      int  = 100,
    limit_sec:      int  = 500,
    limit_img:      int  = 200,
    limit_entity:   int  = 200,
    limit_tbl:      int  = 0,       # 表格节点数量（0=不返回）
    doc_id:         str  = "",      # 按文档筛选
    hide_logos:     bool = True,
    show_level:     int  = 0,       # 章节深度上限（0=不过滤，1=只一级，…）
    show_images:    bool = True,    # 是否返回图片节点
    show_entities:  bool = True,    # 是否返回 Tool/Material/Process/Constraint
    expand_all:     bool = False,   # 忽略所有 LIMIT，返回全部节点
    driver: Driver = Depends(get_driver),
):
    import json as _json, hashlib
    _cache_key = "graph:" + hashlib.md5(
        f"{limit_doc}:{limit_sec}:{limit_img}:{limit_entity}:{limit_tbl}:{doc_id}:{show_level}:{show_images}:{show_entities}:{expand_all}".encode()
    ).hexdigest()[:12]
    try:
        from ..services.cache import get_redis
        _rc = get_redis()
        _cached = _rc.get(_cache_key)
        if _cached:
            return _json.loads(_cached)
    except Exception:
        _rc = None

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
        sec_level_filter = "AND ($show_level = 0 OR coalesce(s.level, 1) <= $show_level)"
        sec_limit_clause = "" if expand_all else "LIMIT $limit_sec"
        sec_result = session.run(f"""
            MATCH (s:Section)
            WHERE ($doc_id = '' OR s.doc_id = $doc_id)
            {sec_level_filter}
            OPTIONAL MATCH (s)-[:HAS_SUBSECTION]->(child:Section)
            WITH s, count(child) AS children_count
            RETURN s.chunk_id AS id,
                   s.title    AS name,
                   s.doc_id   AS doc_id,
                   coalesce(s.level, 1)  AS level,
                   s.number   AS number,
                   children_count > 0   AS has_children,
                   'Section' AS type
            ORDER BY s.doc_id, coalesce(s.level, 1), s.number, s.chunk_id
            {sec_limit_clause}
        """, doc_id=doc_id, limit_sec=limit_sec, show_level=show_level)
        nodes += [
            {
                "id":           r["id"],
                "name":         r["name"] or r["id"],
                "type":         "Section",
                "doc_id":       r["doc_id"] or "",
                "level":        r["level"],
                "number":       r["number"] or "",
                "has_children": bool(r["has_children"]),
            }
            for r in sec_result
        ]

        # ── Image 节点 ────────────────────────────────────────────────────────
        if show_images:
            img_limit_clause = "" if expand_all else "LIMIT $limit"
            img_result = session.run(f"""
                MATCH (i:Image)
                WHERE ($doc_id = '' OR i.doc_id = $doc_id)
                  AND (
                    NOT $hide_logos
                    OR (
                        coalesce(i.is_logo, false) = false
                        AND NOT toLower(coalesce(i.caption, ''))     CONTAINS 'logo'
                        AND NOT toLower(coalesce(i.caption, ''))     CONTAINS '标志'
                        AND NOT toLower(coalesce(i.caption, ''))     CONTAINS '徽标'
                        AND NOT toLower(coalesce(i.caption, ''))     CONTAINS '商标'
                        AND NOT toLower(coalesce(i.description, '')) CONTAINS 'logo'
                        AND NOT toLower(coalesce(i.description, '')) CONTAINS '标志'
                        AND NOT toLower(coalesce(i.description, '')) CONTAINS '徽标'
                        AND NOT toLower(coalesce(i.description, '')) CONTAINS '商标'
                        AND NOT toLower(coalesce(i.keywords, ''))    CONTAINS 'logo'
                        AND NOT toLower(coalesce(i.keywords, ''))    CONTAINS '标志'
                        AND NOT toLower(coalesce(i.keywords, ''))    CONTAINS '徽标'
                        AND NOT toLower(coalesce(i.keywords, ''))    CONTAINS '商标'
                        AND NOT toLower(coalesce(i.path, ''))        CONTAINS 'logo'
                    )
                  )
                RETURN i.image_id AS id, i.caption AS name,
                       i.doc_id AS doc_id, i.description AS description,
                       i.path AS path, i.minio_path AS minio_path,
                       i.is_drawing AS is_drawing
                ORDER BY coalesce(i.page_num, i.page, 0), i.image_id
                {img_limit_clause}
            """, doc_id=doc_id, limit=limit_img, hide_logos=hide_logos)
            for r in img_result:
                image_id = r["id"] or ""
                url = f"/api/images/{image_id}" if image_id and r["minio_path"] else None
                nodes.append({
                    "id":          image_id,
                    "name":        r["name"] or image_id,
                    "type":        "Image",
                    "doc_id":      r["doc_id"] or "",
                    "description": r["description"] or "",
                    "path":        r["path"] or "",
                    "url":         url,
                    "is_drawing":  bool(r["is_drawing"]),
                })

        # ── Tool 节点 ─────────────────────────────────────────────────────────
        entity_limit_clause = "" if expand_all else "LIMIT $limit"
        if show_entities:
            tool_result = session.run(f"""
                MATCH (t:Tool)
                WHERE $doc_id = '' OR t.doc_id = $doc_id
                RETURN t.name AS id, t.name AS name, t.doc_id AS doc_id, 'Tool' AS type
                ORDER BY t.name
                {entity_limit_clause}
            """, doc_id=doc_id, limit=limit_entity)
            nodes += [
                {"id": r["id"], "name": r["name"], "type": "Tool", "doc_id": r["doc_id"] or ""}
                for r in tool_result
            ]

        # ── Material 节点 ─────────────────────────────────────────────────────
        if show_entities:
            mat_result = session.run(f"""
                MATCH (m:Material)
                WHERE $doc_id = '' OR m.doc_id = $doc_id
                RETURN m.name AS id, m.name AS name, m.doc_id AS doc_id, 'Material' AS type
                ORDER BY m.name
                {entity_limit_clause}
            """, doc_id=doc_id, limit=limit_entity)
            nodes += [
                {"id": r["id"], "name": r["name"], "type": "Material", "doc_id": r["doc_id"] or ""}
                for r in mat_result
            ]

        # ── Process 节点 ──────────────────────────────────────────────────────
        if show_entities:
            proc_result = session.run(f"""
                MATCH (p:Process)
                WHERE $doc_id = '' OR p.doc_id = $doc_id
                RETURN p.name AS id, p.name AS name, p.doc_id AS doc_id, 'Process' AS type
                ORDER BY p.name
                {entity_limit_clause}
            """, doc_id=doc_id, limit=limit_entity)
            nodes += [
                {"id": r["id"], "name": r["name"], "type": "Process", "doc_id": r["doc_id"] or ""}
                for r in proc_result
            ]

        # ── Constraint 节点 ───────────────────────────────────────────────────
        if show_entities:
            con_result = session.run(f"""
                MATCH (c:Constraint)
                WHERE $doc_id = '' OR c.doc_id = $doc_id
                RETURN c.constraint_id AS id,
                       c.type + ': ' + c.value + c.unit AS name,
                       c.type AS con_type, c.value AS value, c.value_max AS value_max,
                       c.unit AS unit, c.description AS description,
                       c.standard AS standard, c.doc_id AS doc_id
                ORDER BY c.doc_id, c.constraint_id
                {entity_limit_clause}
            """, doc_id=doc_id, limit=limit_entity)
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

        # ── Table 节点（按需，limit_tbl > 0 才查询）────────────────────────────
        if limit_tbl > 0:
            tbl_result = session.run("""
                MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_TABLE]->(t:Table)
                WHERE $doc_id = '' OR d.name = $doc_id
                RETURN t.table_id AS id,
                       t.doc_id   AS doc_id,
                       t.page_index AS page_index,
                       t.markdown AS markdown,
                       coalesce(t.row_count, size([x IN split(coalesce(t.markdown,''), '\n') WHERE x STARTS WITH '|'])) AS row_count
                LIMIT $limit
            """, doc_id=doc_id, limit=limit_tbl)
            for r in tbl_result:
                md = r["markdown"] or ""
                preview = "\n".join(md.split("\n")[:5])
                nodes.append({
                    "id":          r["id"],
                    "name":        f"表格 p{r['page_index']}",
                    "type":        "Table",
                    "doc_id":      r["doc_id"] or "",
                    "description": preview,
                    "content":     md,
                    "row_count":   r["row_count"] or 2,
                })

        nodes = _append_missing_owner_docs(nodes)
        node_ids = {n["id"] for n in nodes}
        selected_doc_ids = _selected_ids(nodes, "Document")
        selected_section_ids = _selected_ids(nodes, "Section")
        selected_image_ids = _selected_ids(nodes, "Image")
        selected_tool_ids = _selected_ids(nodes, "Tool")
        selected_material_ids = _selected_ids(nodes, "Material")
        selected_process_ids = _selected_ids(nodes, "Process")
        selected_constraint_ids = _selected_ids(nodes, "Constraint")
        selected_table_ids = _selected_ids(nodes, "Table")

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
            WHERE d.name IN $doc_ids AND s.chunk_id IN $section_ids
            RETURN d.name AS source, s.chunk_id AS target, 'HAS_SECTION' AS type
        """, doc_ids=selected_doc_ids, section_ids=selected_section_ids)
        edges += _query_edges("""
            MATCH (d:Document)-[:REFERENCES]->(r:Document)
            WHERE d.name IN $doc_ids AND r.name IN $doc_ids
            RETURN d.name AS source, r.name AS target, 'REFERENCES' AS type
        """, doc_ids=selected_doc_ids)
        edges += _query_edges("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_SUBSECTION]->(c:Section)
            WHERE d.name IN $doc_ids
              AND s.chunk_id IN $section_ids
              AND c.chunk_id IN $section_ids
            RETURN s.chunk_id AS source, c.chunk_id AS target, 'HAS_SUBSECTION' AS type
        """, doc_ids=selected_doc_ids, section_ids=selected_section_ids)
        edges += _query_edges("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_IMAGE]->(i:Image)
            WHERE d.name IN $doc_ids
              AND s.chunk_id IN $section_ids
              AND i.image_id IN $image_ids
            RETURN s.chunk_id AS source, i.image_id AS target, 'HAS_IMAGE' AS type
        """, doc_ids=selected_doc_ids, section_ids=selected_section_ids, image_ids=selected_image_ids)
        edges += _query_edges("""
            MATCH (d:Document)-[:HAS_IMAGE]->(i:Image)
            WHERE d.name IN $doc_ids AND i.image_id IN $image_ids
            RETURN d.name AS source, i.image_id AS target, 'HAS_IMAGE' AS type
        """, doc_ids=selected_doc_ids, image_ids=selected_image_ids)
        if limit_tbl > 0:
            edges += _query_edges("""
                MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_TABLE]->(t:Table)
                WHERE d.name IN $doc_ids
                  AND s.chunk_id IN $section_ids
                  AND t.table_id IN $table_ids
                RETURN s.chunk_id AS source, t.table_id AS target, 'HAS_TABLE' AS type
            """, doc_ids=selected_doc_ids, section_ids=selected_section_ids, table_ids=selected_table_ids)
        edges += _query_edges("""
            MATCH (s:Section)-[:REQUIRES_TOOL]->(t:Tool)
            WHERE s.chunk_id IN $section_ids AND t.name IN $tool_ids
            RETURN s.chunk_id AS source, t.name AS target, 'REQUIRES_TOOL' AS type
        """, section_ids=selected_section_ids, tool_ids=selected_tool_ids)
        edges += _query_edges("""
            MATCH (s:Section)-[:USES_MATERIAL]->(m:Material)
            WHERE s.chunk_id IN $section_ids AND m.name IN $material_ids
            RETURN s.chunk_id AS source, m.name AS target, 'USES_MATERIAL' AS type
        """, section_ids=selected_section_ids, material_ids=selected_material_ids)
        edges += _query_edges("""
            MATCH (s:Section)-[:INVOLVES_PROCESS]->(p:Process)
            WHERE s.chunk_id IN $section_ids AND p.name IN $process_ids
            RETURN s.chunk_id AS source, p.name AS target, 'INVOLVES_PROCESS' AS type
        """, section_ids=selected_section_ids, process_ids=selected_process_ids)
        edges += _query_edges("""
            MATCH (s:Section)-[:HAS_CONSTRAINT]->(c:Constraint)
            WHERE s.chunk_id IN $section_ids AND c.constraint_id IN $constraint_ids
            RETURN s.chunk_id AS source, c.constraint_id AS target, 'HAS_CONSTRAINT' AS type
        """, section_ids=selected_section_ids, constraint_ids=selected_constraint_ids)
        edges += _query_edges("""
            MATCH (p:Process)-[:REQUIRES_TOOL]->(t:Tool)
            WHERE p.name IN $process_ids AND t.name IN $tool_ids
            RETURN p.name AS source, t.name AS target, 'REQUIRES_TOOL' AS type
        """, process_ids=selected_process_ids, tool_ids=selected_tool_ids)
        edges += _query_edges("""
            MATCH (p:Process)-[:USES_MATERIAL]->(m:Material)
            WHERE p.name IN $process_ids AND m.name IN $material_ids
            RETURN p.name AS source, m.name AS target, 'USES_MATERIAL' AS type
        """, process_ids=selected_process_ids, material_ids=selected_material_ids)
        edges += _query_edges("""
            MATCH (a:Material)-[:ALTERNATIVE_TO]->(b:Material)
            WHERE a.name IN $material_ids AND b.name IN $material_ids
            RETURN a.name AS source, b.name AS target, 'ALTERNATIVE_TO' AS type
        """, material_ids=selected_material_ids)
        edges += _query_edges("""
            MATCH (a)-[:COMPATIBLE_WITH]->(b)
            WHERE ((a:Material AND a.name IN $material_ids) OR (a:Tool AND a.name IN $tool_ids))
              AND ((b:Material AND b.name IN $material_ids) OR (b:Tool AND b.name IN $tool_ids))
            RETURN a.name AS source, b.name AS target, 'COMPATIBLE_WITH' AS type
        """, material_ids=selected_material_ids, tool_ids=selected_tool_ids)
        edges += _query_edges("""
            MATCH (i:Image)-[:MENTIONS_TOOL]->(t:Tool)
            WHERE i.image_id IN $image_ids AND t.name IN $tool_ids
            RETURN i.image_id AS source, t.name AS target, 'MENTIONS_TOOL' AS type
        """, image_ids=selected_image_ids, tool_ids=selected_tool_ids)
        edges += _query_edges("""
            MATCH (new_doc:Document)-[:SUPERSEDES]->(old_doc:Document)
            WHERE new_doc.name IN $doc_ids AND old_doc.name IN $doc_ids
            RETURN new_doc.name AS source, old_doc.name AS target, 'SUPERSEDES' AS type
        """, doc_ids=selected_doc_ids)
        edges += _query_edges("""
            MATCH (a:Section)-[r:SIMILAR_TO]-(b:Section)
            WHERE a.chunk_id IN $section_ids
              AND b.chunk_id IN $section_ids
              AND a.chunk_id < b.chunk_id
            RETURN a.chunk_id AS source, b.chunk_id AS target,
                   'SIMILAR_TO' AS type
        """, section_ids=selected_section_ids)

    stats = {
        "total":    len(nodes),
        "docs":     sum(1 for n in nodes if n.get("type") == "Document"),
        "sections": sum(1 for n in nodes if n.get("type") == "Section"),
        "images":   sum(1 for n in nodes if n.get("type") == "Image"),
        "tables":   sum(1 for n in nodes if n.get("type") == "Table"),
        "entities": sum(1 for n in nodes if n.get("type") in ("Tool", "Material", "Process", "Constraint")),
    }
    _result = {"nodes": nodes, "edges": edges, "stats": stats}
    try:
        if _rc: _rc.setex(_cache_key, 60, _json.dumps(_result, default=str))
    except Exception:
        pass
    return _result
