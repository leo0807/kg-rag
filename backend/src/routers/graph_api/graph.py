from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from neo4j import Driver

from ...auth.deps import get_current_user, get_protected_driver
from ...core.database import get_driver
from ...db.models import User
from ...services.graph.graph_helpers import (
    _selected_ids,
    _extend_unique_nodes,
    _owner_doc_ids,
    _load_document_nodes,
    _filter_zero_degree_document_nodes,
    _load_connected_entity_nodes,
    build_edges,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
async def get_graph(
    limit_doc:     int  = 100,
    limit_sec:     int  = 500,
    limit_img:     int  = 200,
    limit_entity:  int  = 200,
    limit_tbl:     int  = 0,
    doc_id:        str  = "",
    hide_logos:    bool = True,
    show_level:    int  = 0,
    show_images:   bool = True,
    show_entities: bool = True,
    expand_all:    bool = False,
    _: User = Depends(get_current_user),
    driver: Driver = Depends(get_protected_driver),
):
    import json as _json, hashlib
    _cache_key = "graph:" + hashlib.md5(
        f"{limit_doc}:{limit_sec}:{limit_img}:{limit_entity}:{limit_tbl}:{doc_id}:{show_level}:{show_images}:{show_entities}:{expand_all}".encode()
    ).hexdigest()[:12]
    try:
        from ...services.infra.cache import get_redis
        _rc = get_redis()
        _cached = _rc.get(_cache_key)
        if _cached:
            return _json.loads(_cached)
    except Exception:
        _rc = None

    with driver.session() as session:
        nodes: list[dict] = []

        sec_level_filter = "AND ($show_level = 0 OR coalesce(s.level, 1) <= $show_level)"
        sec_limit_clause = "" if expand_all else "LIMIT $limit_sec"
        sec_result = session.run(f"""
            MATCH (s:Section)
            WHERE ($doc_id = '' OR s.doc_id = $doc_id)
            {sec_level_filter}
            OPTIONAL MATCH (s)-[:HAS_SUBSECTION]->(child:Section)
            WITH s, count(child) AS children_count
            RETURN s.chunk_id AS id, s.title AS name, s.doc_id AS doc_id,
                   coalesce(s.level, 1) AS level, s.number AS number,
                   children_count > 0 AS has_children, 'Section' AS type
            ORDER BY s.doc_id, coalesce(s.level, 1), s.number, s.chunk_id
            {sec_limit_clause}
        """, doc_id=doc_id, limit_sec=limit_sec, show_level=show_level)
        nodes += [
            {
                "id": r["id"], "name": r["name"] or r["id"], "type": "Section",
                "doc_id": r["doc_id"] or "", "level": r["level"],
                "number": r["number"] or "", "has_children": bool(r["has_children"]),
            }
            for r in sec_result
        ]

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
                        AND NOT toLower(coalesce(i.keywords, ''))    CONTAINS 'logo'
                        AND NOT toLower(coalesce(i.path, ''))        CONTAINS 'logo'
                    )
                  )
                RETURN i.image_id AS id, i.caption AS name, i.doc_id AS doc_id,
                       i.description AS description, i.path AS path,
                       i.minio_path AS minio_path, i.is_drawing AS is_drawing
                ORDER BY coalesce(i.page_num, i.page, 0), i.image_id
                {img_limit_clause}
            """, doc_id=doc_id, limit=limit_img, hide_logos=hide_logos)
            for r in img_result:
                image_id = r["id"] or ""
                url = f"/api/images/{image_id}" if image_id and r["minio_path"] else None
                nodes.append({
                    "id": image_id, "name": r["name"] or image_id, "type": "Image",
                    "doc_id": r["doc_id"] or "", "description": r["description"] or "",
                    "path": r["path"] or "", "url": url, "is_drawing": bool(r["is_drawing"]),
                })

        if show_entities:
            entity_nodes = _load_connected_entity_nodes(
                session,
                doc_id=doc_id,
                section_ids=_selected_ids(nodes, "Section"),
                image_ids=_selected_ids(nodes, "Image"),
                limit=limit_entity,
                expand_all=expand_all,
            )
            nodes = _extend_unique_nodes(nodes, entity_nodes)

        if limit_tbl > 0:
            tbl_result = session.run("""
                MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_TABLE]->(t:Table)
                WHERE $doc_id = '' OR d.name = $doc_id
                RETURN t.table_id AS id, t.doc_id AS doc_id, t.page_index AS page_index,
                       t.markdown AS markdown,
                       coalesce(t.row_count, size([x IN split(coalesce(t.markdown,''), '\n') WHERE x STARTS WITH '|'])) AS row_count
                LIMIT $limit
            """, doc_id=doc_id, limit=limit_tbl)
            for r in tbl_result:
                md = r["markdown"] or ""
                nodes.append({
                    "id": r["id"], "name": f"表格 p{r['page_index']}", "type": "Table",
                    "doc_id": r["doc_id"] or "", "description": "\n".join(md.split("\n")[:5]),
                    "content": md, "row_count": r["row_count"] or 2,
                })

        visible_doc_ids = _owner_doc_ids(nodes)
        if doc_id:
            visible_doc_ids = sorted(set(visible_doc_ids) | {doc_id})

        if visible_doc_ids:
            nodes = _load_document_nodes(session, visible_doc_ids) + nodes
        else:
            doc_result = session.run("""
                MATCH (d:Document)
                WHERE $doc_id = '' OR d.name = $doc_id
                RETURN d.name AS id, coalesce(d.title, d.name) AS name,
                       d.name AS doc_id, d.version AS version, 'Document' AS type
                LIMIT $limit
            """, doc_id=doc_id, limit=limit_doc)
            nodes = [
                {"id": r["id"], "name": r["name"], "doc_id": r["doc_id"],
                 "version": r["version"] or "", "type": "Document"}
                for r in doc_result
            ]

        node_ids = {n["id"] for n in nodes}
        edges = build_edges(
            session,
            node_ids,
            selected_doc_ids=_selected_ids(nodes, "Document"),
            selected_section_ids=_selected_ids(nodes, "Section"),
            selected_image_ids=_selected_ids(nodes, "Image"),
            selected_tool_ids=_selected_ids(nodes, "Tool"),
            selected_material_ids=_selected_ids(nodes, "Material"),
            selected_process_ids=_selected_ids(nodes, "Process"),
            selected_constraint_ids=_selected_ids(nodes, "Constraint"),
            selected_table_ids=_selected_ids(nodes, "Table"),
            limit_tbl=limit_tbl,
        )
        nodes = _filter_zero_degree_document_nodes(
            nodes, edges, keep_doc_ids={doc_id} if doc_id else set()
        )

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
        if _rc:
            _rc.setex(_cache_key, 60, _json.dumps(_result, default=str))
    except Exception:
        pass
    return _result
