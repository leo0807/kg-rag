from __future__ import annotations


def _selected_ids(nodes: list[dict], node_type: str) -> list[str]:
    return [str(n["id"]) for n in nodes if n.get("type") == node_type and n.get("id")]


def _extend_unique_nodes(nodes: list[dict], extra_nodes: list[dict]) -> list[dict]:
    existing_ids = {str(n["id"]) for n in nodes if n.get("id")}
    for node in extra_nodes:
        node_id = str(node.get("id") or "").strip()
        if not node_id or node_id in existing_ids:
            continue
        nodes.append(node)
        existing_ids.add(node_id)
    return nodes


def _append_missing_owner_docs(nodes: list[dict]) -> list[dict]:
    existing_doc_ids = {str(n["id"]) for n in nodes if n.get("type") == "Document" and n.get("id")}
    extras: list[dict] = []
    for node in nodes:
        doc_id = str(node.get("doc_id") or "").strip()
        if not doc_id or doc_id in existing_doc_ids:
            continue
        extras.append({
            "id": doc_id, "name": doc_id, "doc_id": doc_id,
            "version": "", "type": "Document",
        })
        existing_doc_ids.add(doc_id)
    if extras:
        nodes.extend(extras)
    return nodes


def _owner_doc_ids(nodes: list[dict]) -> list[str]:
    doc_ids = {
        str(node.get("doc_id") or "").strip()
        for node in nodes
        if node.get("type") != "Document" and str(node.get("doc_id") or "").strip()
    }
    return sorted(doc_ids)


def _load_document_nodes(session, doc_ids: list[str]) -> list[dict]:
    if not doc_ids:
        return []
    result = session.run("""
        MATCH (d:Document)
        WHERE d.name IN $doc_ids
        RETURN d.name AS id,
               coalesce(d.title, d.name) AS name,
               d.name AS doc_id,
               d.version AS version,
               'Document' AS type
        ORDER BY d.name
    """, doc_ids=doc_ids)
    return [
        {
            "id": row["id"], "name": row["name"], "doc_id": row["doc_id"],
            "version": row["version"] or "", "type": "Document",
        }
        for row in result
    ]


def _filter_zero_degree_document_nodes(
    nodes: list[dict],
    edges: list[dict],
    *,
    keep_doc_ids: set[str] | None = None,
) -> list[dict]:
    keep_doc_ids = keep_doc_ids or set()
    degree: dict[str, int] = {}
    for edge in edges:
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if source:
            degree[source] = degree.get(source, 0) + 1
        if target:
            degree[target] = degree.get(target, 0) + 1
    return [
        node for node in nodes
        if node.get("type") != "Document"
        or str(node.get("id") or "") in keep_doc_ids
        or degree.get(str(node.get("id") or ""), 0) > 0
    ]


def _load_connected_entity_nodes(
    session,
    *,
    doc_id: str,
    section_ids: list[str],
    image_ids: list[str],
    limit: int,
    expand_all: bool,
) -> list[dict]:
    limit_clause = "" if expand_all else "LIMIT $limit"
    if doc_id:
        result = session.run(f"""
            CALL {{
                WITH $section_ids AS section_ids
                UNWIND section_ids AS sid
                MATCH (s:Section {{chunk_id: sid}})-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS|HAS_CONSTRAINT]->(e)
                RETURN DISTINCT e
                UNION
                WITH $image_ids AS image_ids
                UNWIND image_ids AS iid
                MATCH (i:Image {{image_id: iid}})-[:MENTIONS_TOOL|HAS_ANNOTATION]->(e)
                RETURN DISTINCT e
            }}
            RETURN DISTINCT
                CASE WHEN e:Tool THEN e.name WHEN e:Material THEN e.name
                     WHEN e:Process THEN e.name WHEN e:Constraint THEN e.constraint_id ELSE '' END AS id,
                CASE WHEN e:Constraint THEN e.type + ': ' + e.value + e.unit
                     ELSE coalesce(e.name, '') END AS name,
                CASE WHEN e:Tool THEN 'Tool' WHEN e:Material THEN 'Material'
                     WHEN e:Process THEN 'Process' WHEN e:Constraint THEN 'Constraint'
                     ELSE 'Unknown' END AS type,
                e.doc_id AS doc_id, e.type AS con_type, e.value AS value,
                e.value_max AS value_max, e.unit AS unit,
                e.description AS description, e.standard AS standard
            ORDER BY type, name
            {limit_clause}
        """, section_ids=section_ids, image_ids=image_ids, limit=limit)
    else:
        result = session.run(f"""
            MATCH (e)
            WHERE e:Tool OR e:Material OR e:Process OR e:Constraint
            RETURN
                CASE WHEN e:Tool THEN e.name WHEN e:Material THEN e.name
                     WHEN e:Process THEN e.name WHEN e:Constraint THEN e.constraint_id ELSE '' END AS id,
                CASE WHEN e:Constraint THEN e.type + ': ' + e.value + e.unit
                     ELSE coalesce(e.name, '') END AS name,
                CASE WHEN e:Tool THEN 'Tool' WHEN e:Material THEN 'Material'
                     WHEN e:Process THEN 'Process' WHEN e:Constraint THEN 'Constraint'
                     ELSE 'Unknown' END AS type,
                e.doc_id AS doc_id, e.type AS con_type, e.value AS value,
                e.value_max AS value_max, e.unit AS unit,
                e.description AS description, e.standard AS standard
            ORDER BY type, name
            {limit_clause}
        """, limit=limit)

    out: list[dict] = []
    for r in result:
        node = {"id": r["id"], "name": r["name"] or r["id"], "type": r["type"], "doc_id": r["doc_id"] or ""}
        if r["type"] == "Constraint":
            node.update({
                "con_type": r["con_type"], "value": r["value"],
                "value_max": r["value_max"] or "", "unit": r["unit"],
                "description": r["description"] or "", "standard": r["standard"] or "",
            })
        out.append(node)
    return out


def build_edges(session, node_ids: set[str], *, selected_doc_ids, selected_section_ids,
                selected_image_ids, selected_tool_ids, selected_material_ids,
                selected_process_ids, selected_constraint_ids, selected_table_ids,
                limit_tbl: int = 0) -> list[dict]:
    def _q(cypher: str, **params):
        result = session.run(cypher, **params)
        return [dict(r) for r in result if r["source"] in node_ids and r["target"] in node_ids]

    edges = []
    edges += _q("""
        MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
        WHERE d.name IN $doc_ids AND s.chunk_id IN $section_ids
        RETURN d.name AS source, s.chunk_id AS target, 'HAS_SECTION' AS type
    """, doc_ids=selected_doc_ids, section_ids=selected_section_ids)
    edges += _q("""
        MATCH (d:Document)-[:REFERENCES]->(r:Document)
        WHERE d.name IN $doc_ids AND r.name IN $doc_ids
        RETURN d.name AS source, r.name AS target, 'REFERENCES' AS type
    """, doc_ids=selected_doc_ids)
    edges += _q("""
        MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_SUBSECTION]->(c:Section)
        WHERE d.name IN $doc_ids AND s.chunk_id IN $section_ids AND c.chunk_id IN $section_ids
        RETURN s.chunk_id AS source, c.chunk_id AS target, 'HAS_SUBSECTION' AS type
    """, doc_ids=selected_doc_ids, section_ids=selected_section_ids)
    edges += _q("""
        MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_IMAGE]->(i:Image)
        WHERE d.name IN $doc_ids AND s.chunk_id IN $section_ids AND i.image_id IN $image_ids
        RETURN s.chunk_id AS source, i.image_id AS target, 'HAS_IMAGE' AS type
    """, doc_ids=selected_doc_ids, section_ids=selected_section_ids, image_ids=selected_image_ids)
    edges += _q("""
        MATCH (d:Document)-[:HAS_IMAGE]->(i:Image)
        WHERE d.name IN $doc_ids AND i.image_id IN $image_ids
        RETURN d.name AS source, i.image_id AS target, 'HAS_IMAGE' AS type
    """, doc_ids=selected_doc_ids, image_ids=selected_image_ids)
    if limit_tbl > 0:
        edges += _q("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_TABLE]->(t:Table)
            WHERE d.name IN $doc_ids AND s.chunk_id IN $section_ids AND t.table_id IN $table_ids
            RETURN s.chunk_id AS source, t.table_id AS target, 'HAS_TABLE' AS type
        """, doc_ids=selected_doc_ids, section_ids=selected_section_ids, table_ids=selected_table_ids)
    edges += _q("""
        MATCH (s:Section)-[:REQUIRES_TOOL]->(t:Tool)
        WHERE s.chunk_id IN $section_ids AND t.name IN $tool_ids
        RETURN s.chunk_id AS source, t.name AS target, 'REQUIRES_TOOL' AS type
    """, section_ids=selected_section_ids, tool_ids=selected_tool_ids)
    edges += _q("""
        MATCH (s:Section)-[:USES_MATERIAL]->(m:Material)
        WHERE s.chunk_id IN $section_ids AND m.name IN $material_ids
        RETURN s.chunk_id AS source, m.name AS target, 'USES_MATERIAL' AS type
    """, section_ids=selected_section_ids, material_ids=selected_material_ids)
    edges += _q("""
        MATCH (s:Section)-[:INVOLVES_PROCESS]->(p:Process)
        WHERE s.chunk_id IN $section_ids AND p.name IN $process_ids
        RETURN s.chunk_id AS source, p.name AS target, 'INVOLVES_PROCESS' AS type
    """, section_ids=selected_section_ids, process_ids=selected_process_ids)
    edges += _q("""
        MATCH (s:Section)-[:HAS_CONSTRAINT]->(c:Constraint)
        WHERE s.chunk_id IN $section_ids AND c.constraint_id IN $constraint_ids
        RETURN s.chunk_id AS source, c.constraint_id AS target, 'HAS_CONSTRAINT' AS type
    """, section_ids=selected_section_ids, constraint_ids=selected_constraint_ids)
    edges += _q("""
        MATCH (p:Process)-[:REQUIRES_TOOL]->(t:Tool)
        WHERE p.name IN $process_ids AND t.name IN $tool_ids
        RETURN p.name AS source, t.name AS target, 'REQUIRES_TOOL' AS type
    """, process_ids=selected_process_ids, tool_ids=selected_tool_ids)
    edges += _q("""
        MATCH (p:Process)-[:USES_MATERIAL]->(m:Material)
        WHERE p.name IN $process_ids AND m.name IN $material_ids
        RETURN p.name AS source, m.name AS target, 'USES_MATERIAL' AS type
    """, process_ids=selected_process_ids, material_ids=selected_material_ids)
    edges += _q("""
        MATCH (a:Material)-[:ALTERNATIVE_TO]->(b:Material)
        WHERE a.name IN $material_ids AND b.name IN $material_ids
        RETURN a.name AS source, b.name AS target, 'ALTERNATIVE_TO' AS type
    """, material_ids=selected_material_ids)
    edges += _q("""
        MATCH (a)-[:COMPATIBLE_WITH]->(b)
        WHERE ((a:Material AND a.name IN $material_ids) OR (a:Tool AND a.name IN $tool_ids))
          AND ((b:Material AND b.name IN $material_ids) OR (b:Tool AND b.name IN $tool_ids))
        RETURN a.name AS source, b.name AS target, 'COMPATIBLE_WITH' AS type
    """, material_ids=selected_material_ids, tool_ids=selected_tool_ids)
    edges += _q("""
        MATCH (i:Image)-[:MENTIONS_TOOL]->(t:Tool)
        WHERE i.image_id IN $image_ids AND t.name IN $tool_ids
        RETURN i.image_id AS source, t.name AS target, 'MENTIONS_TOOL' AS type
    """, image_ids=selected_image_ids, tool_ids=selected_tool_ids)
    edges += _q("""
        MATCH (i:Image)-[:HAS_ANNOTATION]->(c:Constraint)
        WHERE i.image_id IN $image_ids AND c.constraint_id IN $constraint_ids
        RETURN i.image_id AS source, c.constraint_id AS target, 'HAS_ANNOTATION' AS type
    """, image_ids=selected_image_ids, constraint_ids=selected_constraint_ids)
    edges += _q("""
        MATCH (new_doc:Document)-[:SUPERSEDES]->(old_doc:Document)
        WHERE new_doc.name IN $doc_ids AND old_doc.name IN $doc_ids
        RETURN new_doc.name AS source, old_doc.name AS target, 'SUPERSEDES' AS type
    """, doc_ids=selected_doc_ids)
    edges += _q("""
        MATCH (a:Section)-[r:SIMILAR_TO]-(b:Section)
        WHERE a.chunk_id IN $section_ids AND b.chunk_id IN $section_ids AND a.chunk_id < b.chunk_id
        RETURN a.chunk_id AS source, b.chunk_id AS target, 'SIMILAR_TO' AS type
    """, section_ids=selected_section_ids)
    return edges


def load_reference_target_stubs(
    session,
    selected_doc_ids: list[str],
    known_node_ids: set[str],
) -> tuple[list[dict], list[dict]]:
    """Return (stub_nodes, edges) for REFERENCES targets not already in the node set."""
    if not selected_doc_ids:
        return [], []
    result = session.run("""
        MATCH (d:Document)-[:REFERENCES]->(r:Document)
        WHERE d.name IN $doc_ids AND NOT r.name IN $known_ids
        RETURN DISTINCT d.name AS source, r.name AS target,
               coalesce(r.title, r.name) AS target_name
    """, doc_ids=selected_doc_ids, known_ids=list(known_node_ids))

    stub_nodes: list[dict] = []
    extra_edges: list[dict] = []
    seen: set[str] = set()
    for row in result:
        target_id = str(row["target"] or "").strip()
        source_id = str(row["source"] or "").strip()
        if not target_id or not source_id:
            continue
        extra_edges.append({"source": source_id, "target": target_id, "type": "REFERENCES"})
        if target_id not in seen:
            seen.add(target_id)
            stub_nodes.append({
                "id": target_id,
                "name": row["target_name"] or target_id,
                "doc_id": target_id,
                "version": "",
                "type": "Document",
                "is_reference_target": True,
            })
    return stub_nodes, extra_edges
