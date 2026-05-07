from __future__ import annotations

from .lazy_loading import _doc_node, _section_node, _unique_nodes, _unique_edges


def search_graph(session, q: str, limit: int = 20) -> dict:
    query = (q or "").strip().lower()
    if not query:
        return {"nodes": [], "edges": [], "stats": {}}

    matched_nodes: list[dict] = []

    doc_rows = session.run(
        """
        MATCH (d:Document)
        WHERE toLower(coalesce(d.title, d.name, '')) CONTAINS $q
           OR toLower(coalesce(d.name, '')) CONTAINS $q
        RETURN d.name AS id, coalesce(d.title, d.name) AS name, d.name AS doc_id,
               d.version AS version
        ORDER BY coalesce(d.title, d.name), d.name
        LIMIT $limit
        """,
        q=query,
        limit=limit,
    )
    matched_nodes.extend(_doc_node(row) for row in doc_rows)

    sec_rows = session.run(
        """
        MATCH (s:Section)
        WHERE toLower(coalesce(s.title, '')) CONTAINS $q
           OR toLower(coalesce(s.content, '')) CONTAINS $q
           OR toLower(coalesce(s.number, '')) CONTAINS $q
        RETURN s.chunk_id AS id, s.title AS name, s.doc_id AS doc_id,
               s.level AS level, s.number AS number, s.page_idx AS page_idx,
               s.bbox AS bbox
        ORDER BY coalesce(s.level, 1), s.doc_id, s.number, s.chunk_id
        LIMIT $limit
        """,
        q=query,
        limit=limit,
    )
    matched_nodes.extend(_section_node(row) for row in sec_rows)

    matched_nodes = _unique_nodes(matched_nodes)[:limit]
    doc_ids = [n["id"] for n in matched_nodes if n["type"] == "Document"]
    sec_ids = [n["id"] for n in matched_nodes if n["type"] == "Section"]

    neighbor_nodes: list[dict] = []
    edges: list[dict] = []

    if doc_ids:
        ref_rows = session.run(
            """
            MATCH (d:Document)-[:REFERENCES]->(r:Document)
            WHERE d.name IN $ids
            RETURN d.name AS source, r.name AS target, 'REFERENCES' AS type
            """,
            ids=doc_ids,
        )
        for row in ref_rows:
            edges.append({"source": row["source"], "target": row["target"], "type": row["type"]})
            if row["source"] not in {n["id"] for n in matched_nodes}:
                neighbor_nodes.append({"id": row["source"], "name": row["source"], "doc_id": row["source"], "type": "Document"})
            if row["target"] not in {n["id"] for n in matched_nodes}:
                neighbor_nodes.append({"id": row["target"], "name": row["target"], "doc_id": row["target"], "type": "Document"})

        sec_neighbor_rows = session.run(
            """
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
            WHERE d.name IN $ids
            RETURN d.name AS source, s.chunk_id AS target, 'HAS_SECTION' AS type
            """,
            ids=doc_ids,
        )
        for row in sec_neighbor_rows:
            edges.append({"source": row["source"], "target": row["target"], "type": row["type"]})

    if sec_ids:
        sub_rows = session.run(
            """
            MATCH (p:Section)-[:HAS_SUBSECTION]->(c:Section)
            WHERE p.chunk_id IN $ids
            RETURN p.chunk_id AS source, c.chunk_id AS target, 'HAS_SUBSECTION' AS type
            """,
            ids=sec_ids,
        )
        for row in sub_rows:
            edges.append({"source": row["source"], "target": row["target"], "type": row["type"]})

        img_rows = session.run(
            """
            MATCH (p:Section)-[:HAS_IMAGE]->(i:Image)
            WHERE p.chunk_id IN $ids
            RETURN p.chunk_id AS source, i.image_id AS target, 'HAS_IMAGE' AS type
            """,
            ids=sec_ids,
        )
        for row in img_rows:
            edges.append({"source": row["source"], "target": row["target"], "type": row["type"]})

        tbl_rows = session.run(
            """
            MATCH (p:Section)-[:HAS_TABLE]->(t:Table)
            WHERE p.chunk_id IN $ids
            RETURN p.chunk_id AS source, t.table_id AS target, 'HAS_TABLE' AS type
            """,
            ids=sec_ids,
        )
        for row in tbl_rows:
            edges.append({"source": row["source"], "target": row["target"], "type": row["type"]})

    nodes = _unique_nodes(matched_nodes + neighbor_nodes)
    edges = _unique_edges(edges)
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "matched": len(matched_nodes),
            "neighbors": max(0, len(nodes) - len(matched_nodes)),
            "edges": len(edges),
        },
    }
