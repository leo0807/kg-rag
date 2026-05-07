from __future__ import annotations


def _unique_nodes(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for node in nodes:
        node_id = str(node.get("id") or "").strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        out.append(node)
    return out


def _unique_edges(edges: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (str(edge.get("source") or ""), str(edge.get("target") or ""), str(edge.get("type") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(edge)
    return out


def _doc_node(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"] or row["id"],
        "doc_id": row["doc_id"] or row["id"],
        "version": row.get("version") or "",
        "type": "Document",
        "ref_degree": int(row.get("ref_degree") or 0),
    }


def _section_node(row) -> dict:
    node = {
        "id": row["id"],
        "name": row["name"] or row["id"],
        "doc_id": row["doc_id"] or "",
        "type": "Section",
        "level": int(row.get("level") or 1),
        "number": row.get("number") or "",
        "has_children": bool(row.get("has_children")),
    }
    if row.get("page_idx") is not None:
        node["page_idx"] = row.get("page_idx")
    if row.get("bbox") is not None:
        node["bbox"] = row.get("bbox")
    return node


def _image_node(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"] or row["id"],
        "doc_id": row["doc_id"] or "",
        "type": "Image",
        "description": row.get("description") or "",
        "path": row.get("path") or "",
        "url": row.get("url"),
        "is_drawing": bool(row.get("is_drawing")),
        "page_num": row.get("page_num"),
    }


def _table_node(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"] or row["id"],
        "doc_id": row["doc_id"] or "",
        "type": "Table",
        "page_index": row.get("page_index"),
        "description": row.get("description") or "",
        "content": row.get("content") or "",
        "row_count": row.get("row_count") or 0,
    }


def load_overview(session, limit: int = 100) -> dict:
    docs_result = session.run(
        """
        MATCH (d:Document)
        WHERE (d)-[:REFERENCES]-()
        OPTIONAL MATCH (d)-[r:REFERENCES]-()
        WITH d, count(r) AS ref_degree
        RETURN d.name AS id, coalesce(d.title, d.name) AS name, d.name AS doc_id,
               d.version AS version, ref_degree
        ORDER BY ref_degree DESC, d.name
        LIMIT $limit
        """,
        limit=limit,
    )
    docs = [_doc_node(row) for row in docs_result]
    ids = [d["id"] for d in docs]
    edge_result = session.run(
        """
        MATCH (a:Document)-[r:REFERENCES]->(b:Document)
        WHERE a.name IN $ids AND b.name IN $ids
        RETURN a.name AS source, b.name AS target, 'REFERENCES' AS type, count(r) AS weight
        """,
        ids=ids,
    )
    edges = [{"source": r["source"], "target": r["target"], "type": r["type"], "weight": r["weight"]} for r in edge_result]
    return {
        "nodes": docs,
        "edges": edges,
        "stats": {
            "total_docs": len(docs),
            "total_refs": sum(int(e.get("weight") or 1) for e in edges),
        },
    }


def expand_document(session, doc_id: str, limit: int = 50) -> dict:
    doc_row = session.run(
        """
        MATCH (d:Document {name: $doc_id})
        RETURN d.name AS id, coalesce(d.title, d.name) AS name, d.name AS doc_id,
               d.version AS version
        """,
        doc_id=doc_id,
    ).single()
    if not doc_row:
        return {"nodes": [], "edges": [], "stats": {}}

    sec_result = session.run(
        """
        MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
        WHERE coalesce(s.level, 1) = 1
        OPTIONAL MATCH (s)-[:HAS_SUBSECTION]->(child:Section)
        WITH s, count(child) AS has_children
        RETURN s.chunk_id AS id, s.title AS name, s.doc_id AS doc_id,
               s.level AS level, s.number AS number, s.page_idx AS page_idx,
               s.bbox AS bbox, has_children > 0 AS has_children
        ORDER BY coalesce(s.seq_index, 0), s.number, s.chunk_id
        LIMIT $limit
        """,
        doc_id=doc_id,
        limit=limit,
    )
    sections = [_section_node(row) for row in sec_result]
    nodes = _unique_nodes([_doc_node(doc_row)] + sections)
    edges = [{"source": doc_id, "target": sec["id"], "type": "HAS_SECTION"} for sec in sections]
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {"total_nodes": len(nodes), "section_nodes": len(sections)},
    }


def expand_section(session, chunk_id: str, limit: int = 30) -> dict:
    parent_row = session.run(
        """
        MATCH (s:Section {chunk_id: $chunk_id})
        RETURN s.chunk_id AS id, s.title AS name, s.doc_id AS doc_id,
               s.level AS level, s.number AS number, s.page_idx AS page_idx,
               s.bbox AS bbox
        """,
        chunk_id=chunk_id,
    ).single()
    if not parent_row:
        return {"nodes": [], "edges": [], "stats": {}}

    rows = session.run(
        """
        CALL {
            MATCH (p:Section {chunk_id: $chunk_id})-[:HAS_SUBSECTION]->(child:Section)
            RETURN child.chunk_id AS id, child.title AS name, child.doc_id AS doc_id,
                   'Section' AS type, child.level AS level, child.number AS number,
                   child.page_idx AS page_idx, child.bbox AS bbox, false AS is_drawing,
                   null AS page_num, null AS page_index, null AS description,
                   null AS content, null AS row_count, null AS path, null AS url
            UNION ALL
            MATCH (p:Section {chunk_id: $chunk_id})-[:HAS_IMAGE]->(i:Image)
            RETURN i.image_id AS id, i.caption AS name, i.doc_id AS doc_id,
                   'Image' AS type, null AS level, null AS number,
                   null AS page_idx, null AS bbox, coalesce(i.is_drawing, false) AS is_drawing,
                   coalesce(i.page_num, i.page) AS page_num, null AS page_index,
                   i.description AS description, null AS content, null AS row_count,
                   i.path AS path,
                   CASE WHEN i.minio_path IS NOT NULL THEN '/api/images/' + i.image_id ELSE null END AS url
            UNION ALL
            MATCH (p:Section {chunk_id: $chunk_id})-[:HAS_TABLE]->(t:Table)
            RETURN t.table_id AS id, coalesce(t.title, t.table_id) AS name, t.doc_id AS doc_id,
                   'Table' AS type, null AS level, null AS number,
                   null AS page_idx, null AS bbox, false AS is_drawing,
                   null AS page_num, t.page_index AS page_index,
                   coalesce(t.title, '') AS description, t.markdown AS content,
                   coalesce(t.row_count, 0) AS row_count, null AS path, null AS url
        }
        RETURN *
        LIMIT $limit
        """,
        chunk_id=chunk_id,
        limit=limit,
    )

    children: list[dict] = []
    edges: list[dict] = []
    for row in rows:
        node_type = row["type"]
        if node_type == "Section":
            node = _section_node(row)
            edges.append({"source": chunk_id, "target": node["id"], "type": "HAS_SUBSECTION"})
        elif node_type == "Image":
            node = _image_node(row)
            edges.append({"source": chunk_id, "target": node["id"], "type": "HAS_IMAGE"})
        else:
            node = _table_node(row)
            edges.append({"source": chunk_id, "target": node["id"], "type": "HAS_TABLE"})
        children.append(node)

    nodes = _unique_nodes([_section_node(parent_row)] + children)
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {"total_nodes": len(nodes), "child_nodes": len(children)},
    }
