from __future__ import annotations

import json
import logging

from neo4j import Driver

from .entity_writer_support import TYPE_LABEL, collect_section_entities

logger = logging.getLogger(__name__)


def _parse_rows(rows_json_str: str) -> list[list[str]]:
    try:
        return json.loads(rows_json_str) if rows_json_str else []
    except Exception:
        return []


def _build_structured_data(headers: list[str], data_rows: list[list[str]]) -> str:
    if not headers or not data_rows:
        return "[]"
    records = []
    for row in data_rows:
        records.append({headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))})
    return json.dumps(records, ensure_ascii=False)


def write_tables(driver: Driver, doc_id: str, table_data: list[dict]) -> None:
    total_tables = total_rows = 0
    with driver.session() as session:
        for item in table_data:
            table_id = item["table_id"]
            chunk_id = item["chunk_id"]
            raw_rows = _parse_rows(item.get("rows_json", ""))
            headers = raw_rows[0] if raw_rows else []
            data_rows = raw_rows[1:] if len(raw_rows) > 1 else []
            session.run(
                """
                MATCH (sec:Section {chunk_id: $chunk_id})
                MERGE (t:Table {table_id: $table_id})
                SET t.doc_id          = $doc_id,
                    t.markdown        = $markdown,
                    t.rows_json       = $rows_json,
                    t.page_index      = $page_index,
                    t.row_count       = $row_count,
                    t.col_count       = $col_count,
                    t.bbox            = $bbox,
                    t.headers         = $headers,
                    t.structured_data = $structured_data
                MERGE (sec)-[:HAS_TABLE]->(t)
                """,
                chunk_id=chunk_id,
                table_id=table_id,
                doc_id=doc_id,
                markdown=item["markdown"],
                rows_json=item["rows_json"],
                page_index=item["page_index"],
                row_count=item.get("row_count", 0),
                col_count=len(headers),
                bbox=item.get("bbox"),
                headers=headers,
                structured_data=_build_structured_data(headers, data_rows),
            )
            total_tables += 1
            for constraint in item.get("constraints", []):
                session.run(
                    """
                    MATCH (t:Table {table_id: $table_id})
                    MERGE (con:Constraint {constraint_id: $cid})
                    SET con.type        = $type,
                        con.value       = $value,
                        con.value_min   = $value_min,
                        con.value_max   = $value_max,
                        con.unit        = $unit,
                        con.description = $description,
                        con.doc_id      = $doc_id,
                        con.source      = 'table'
                    MERGE (t)-[:HAS_ROW]->(con)
                    WITH t, con
                    MATCH (sec:Section)-[:HAS_TABLE]->(t)
                    MERGE (sec)-[:HAS_CONSTRAINT]->(con)
                    """,
                    table_id=table_id,
                    cid=constraint["constraint_id"],
                    type=constraint["type"],
                    value=constraint["value"],
                    value_min=constraint.get("value_min", ""),
                    value_max=constraint.get("value_max", ""),
                    unit=constraint["unit"],
                    description=constraint.get("description", ""),
                    doc_id=doc_id,
                )
                total_rows += 1
    logger.info("表格写入完成 doc_id=%s tables=%d rows=%d", doc_id, total_tables, total_rows)


def write_entities(driver: Driver, doc_id: str, entity_data: list[dict]) -> None:
    tools_total = materials_total = processes_total = relations_total = 0
    with driver.session() as session:
        for item in entity_data:
            chunk_id = item.get("chunk_id", "")
            tools, materials, processes, relations = collect_section_entities(item)
            if tools:
                session.run(
                    """
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $tools AS name
                    MERGE (t:Tool {name: name})
                    ON CREATE SET t.doc_id = $doc_id
                    MERGE (sec)-[:REQUIRES_TOOL]->(t)
                    """,
                    chunk_id=chunk_id,
                    tools=tools,
                    doc_id=doc_id,
                )
                tools_total += len(tools)
            if materials:
                session.run(
                    """
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $materials AS name
                    MERGE (m:Material {name: name})
                    ON CREATE SET m.doc_id = $doc_id
                    MERGE (sec)-[:USES_MATERIAL]->(m)
                    """,
                    chunk_id=chunk_id,
                    materials=materials,
                    doc_id=doc_id,
                )
                materials_total += len(materials)
            if processes:
                session.run(
                    """
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $processes AS name
                    MERGE (p:Process {name: name})
                    ON CREATE SET p.doc_id = $doc_id
                    MERGE (sec)-[:INVOLVES_PROCESS]->(p)
                    """,
                    chunk_id=chunk_id,
                    processes=processes,
                    doc_id=doc_id,
                )
                processes_total += len(processes)
            for rel in relations:
                from_label = TYPE_LABEL[rel["from_type"]]
                to_label = TYPE_LABEL[rel["to_type"]]
                rel_type = rel["rel"]
                session.run(
                    f"""
                    MERGE (a:{from_label} {{name: $from_name}})
                    ON CREATE SET a.doc_id = $doc_id
                    MERGE (b:{to_label} {{name: $to_name}})
                    ON CREATE SET b.doc_id = $doc_id
                    MERGE (a)-[:{rel_type}]->(b)
                    """,
                    from_name=rel["from_name"].strip(),
                    to_name=rel["to_name"].strip(),
                    doc_id=doc_id,
                )
                relations_total += 1
    logger.info(
        "实体写入完成 doc_id=%s tools=%d materials=%d processes=%d inter_relations=%d",
        doc_id,
        tools_total,
        materials_total,
        processes_total,
        relations_total,
    )


def write_constraints(driver: Driver, doc_id: str, constraint_data: list[dict]) -> None:
    total = 0
    with driver.session() as session:
        for item in constraint_data:
            chunk_id = item.get("chunk_id", "")
            constraints = item.get("constraints", [])
            if not constraints:
                continue
            for constraint in constraints:
                constraint_id = f"{chunk_id}_{constraint['type']}_{constraint['value']}{constraint['unit']}"
                session.run(
                    """
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    MERGE (con:Constraint {constraint_id: $cid})
                    SET con.type        = $type,
                        con.value       = $value,
                        con.value_max   = $value_max,
                        con.unit        = $unit,
                        con.description = $description,
                        con.standard    = $standard,
                        con.doc_id      = $doc_id,
                        con.source      = 'text'
                    MERGE (sec)-[:HAS_CONSTRAINT]->(con)
                    """,
                    chunk_id=chunk_id,
                    cid=constraint_id,
                    type=constraint["type"],
                    value=constraint["value"],
                    value_max=constraint.get("value_max", ""),
                    unit=constraint["unit"],
                    description=constraint.get("description", ""),
                    standard=constraint.get("standard", ""),
                    doc_id=doc_id,
                )
                total += 1
    logger.info("约束写入完成 doc_id=%s constraints=%d", doc_id, total)


def write_drawing_constraints(driver: Driver, image_id: str, doc_id: str, annotations: list[dict]) -> None:
    total = 0
    with driver.session() as session:
        for annotation in annotations:
            raw = annotation.get("raw", "").strip()
            if not raw and not annotation.get("value"):
                continue
            constraint_id = f"{image_id}_{annotation.get('type','other')}_{raw[:20]}"
            session.run(
                """
                MATCH (i:Image {image_id: $image_id})
                MERGE (con:Constraint {constraint_id: $cid})
                SET con.type        = $type,
                    con.value       = $value,
                    con.value_max   = $value_max,
                    con.value_min   = $value_min,
                    con.unit        = $unit,
                    con.description = $parameter,
                    con.standard    = $raw,
                    con.doc_id      = $doc_id,
                    con.source      = 'drawing'
                MERGE (i)-[:HAS_ANNOTATION]->(con)
                """,
                image_id=image_id,
                cid=constraint_id,
                type=annotation.get("type", "other"),
                value=annotation.get("value", ""),
                value_max=annotation.get("value_max", ""),
                value_min=annotation.get("value_min", ""),
                unit=annotation.get("unit", ""),
                parameter=annotation.get("parameter", ""),
                raw=raw,
                doc_id=doc_id,
            )
            session.run(
                """
                MATCH (s:Section)-[:HAS_IMAGE]->(i:Image {image_id: $image_id})
                MATCH (con:Constraint {constraint_id: $cid})
                MERGE (s)-[:HAS_CONSTRAINT]->(con)
                """,
                image_id=image_id,
                cid=constraint_id,
            )
            session.run(
                """
                MATCH (i:Image {image_id: $image_id})
                WHERE NOT EXISTS { MATCH (:Section)-[:HAS_IMAGE]->(i) }
                MATCH (s:Section {doc_id: $doc_id})
                WHERE coalesce(s.page_idx, -1) <= coalesce(i.page_num, i.page, 1) - 1
                WITH i, s
                ORDER BY coalesce(s.page_idx, -1) DESC, coalesce(s.seq_index, -1) DESC
                LIMIT 1
                MATCH (con:Constraint {constraint_id: $cid})
                MERGE (s)-[:HAS_IMAGE]->(i)
                MERGE (s)-[:HAS_CONSTRAINT]->(con)
                """,
                image_id=image_id,
                doc_id=doc_id,
                cid=constraint_id,
            )
            total += 1
    logger.info("图纸约束写入完成 image_id=%s constraints=%d", image_id, total)


def link_image_tools(driver: Driver, image_id: str, tools: list[str]) -> None:
    if not tools:
        return
    with driver.session() as session:
        session.run(
            """
            MATCH (i:Image {image_id: $image_id})
            UNWIND $tools AS tool_name
            MERGE (t:Tool {name: tool_name})
            MERGE (i)-[:MENTIONS_TOOL]->(t)
            """,
            image_id=image_id,
            tools=[tool.strip() for tool in tools if tool and tool.strip()],
        )

