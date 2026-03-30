"""
src/services/entity_writer.py
将实体节点、实体间关系、工艺约束写入 Neo4j 知识图谱

节点类型：
  Tool       (:Tool {name})
  Material   (:Material {name})
  Process    (:Process {name})
  Constraint (:Constraint {type, value, value_max, unit, description, standard})

Section → 实体：
  (Section)-[:REQUIRES_TOOL]->(:Tool)
  (Section)-[:USES_MATERIAL]->(:Material)
  (Section)-[:INVOLVES_PROCESS]->(:Process)
  (Section)-[:HAS_CONSTRAINT]->(:Constraint)

实体间：
  (Process)-[:REQUIRES_TOOL]->(:Tool)
  (Process)-[:USES_MATERIAL]->(:Material)
  (Material)-[:ALTERNATIVE_TO]->(:Material)
  (Material)-[:COMPATIBLE_WITH]->(:Material | :Tool)

图片 → 实体：
  (Image)-[:MENTIONS_TOOL]->(:Tool)
"""
import logging
from neo4j import Driver

logger = logging.getLogger(__name__)

# 允许写入的实体间关系类型
_ALLOWED_RELATIONS = {"REQUIRES_TOOL", "USES_MATERIAL", "ALTERNATIVE_TO", "COMPATIBLE_WITH"}

# 实体 label 映射
_TYPE_LABEL = {"Tool": "Tool", "Material": "Material", "Process": "Process"}


def write_entities(driver: Driver, doc_id: str, entity_data: list[dict]) -> None:
    """
    entity_data: [{
        "chunk_id",
        "tools", "materials", "processes",
        "relations": [{"from_type","from_name","rel","to_type","to_name"}]
    }]
    """
    tools_total = materials_total = processes_total = relations_total = 0

    with driver.session() as session:
        for item in entity_data:
            chunk_id  = item.get("chunk_id", "")
            tools     = [t.strip() for t in item.get("tools", [])     if t and t.strip()]
            materials = [m.strip() for m in item.get("materials", []) if m and m.strip()]
            processes = [p.strip() for p in item.get("processes", []) if p and p.strip()]
            relations = [r for r in item.get("relations", [])
                         if r.get("rel") in _ALLOWED_RELATIONS
                         and r.get("from_type") in _TYPE_LABEL
                         and r.get("to_type")   in _TYPE_LABEL]

            if tools:
                session.run("""
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $tools AS name
                    MERGE (t:Tool {name: name})
                    ON CREATE SET t.doc_id = $doc_id
                    MERGE (sec)-[:REQUIRES_TOOL]->(t)
                """, chunk_id=chunk_id, tools=tools, doc_id=doc_id)
                tools_total += len(tools)

            if materials:
                session.run("""
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $materials AS name
                    MERGE (m:Material {name: name})
                    ON CREATE SET m.doc_id = $doc_id
                    MERGE (sec)-[:USES_MATERIAL]->(m)
                """, chunk_id=chunk_id, materials=materials, doc_id=doc_id)
                materials_total += len(materials)

            if processes:
                session.run("""
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $processes AS name
                    MERGE (p:Process {name: name})
                    ON CREATE SET p.doc_id = $doc_id
                    MERGE (sec)-[:INVOLVES_PROCESS]->(p)
                """, chunk_id=chunk_id, processes=processes, doc_id=doc_id)
                processes_total += len(processes)

            # ── 实体间关系 ──────────────────────────────────────
            for rel in relations:
                from_label = _TYPE_LABEL[rel["from_type"]]
                to_label   = _TYPE_LABEL[rel["to_type"]]
                rel_type   = rel["rel"]
                # Cypher 不支持参数化 label/rel_type，用字符串拼接（值已白名单校验）
                session.run(f"""
                    MERGE (a:{from_label} {{name: $from_name}})
                    MERGE (b:{to_label}   {{name: $to_name}})
                    MERGE (a)-[:{rel_type}]->(b)
                """, from_name=rel["from_name"].strip(), to_name=rel["to_name"].strip())
                relations_total += 1

    logger.info(
        "实体写入完成 doc_id=%s tools=%d materials=%d processes=%d inter_relations=%d",
        doc_id, tools_total, materials_total, processes_total, relations_total,
    )


def write_constraints(driver: Driver, doc_id: str, constraint_data: list[dict]) -> None:
    """
    constraint_data: [{"chunk_id", "constraints": [{
        "type","value","value_max","unit","description","standard"
    }]}]
    新增 Constraint 节点并建立 (Section)-[:HAS_CONSTRAINT]->(Constraint)
    """
    total = 0
    with driver.session() as session:
        for item in constraint_data:
            chunk_id    = item.get("chunk_id", "")
            constraints = item.get("constraints", [])
            if not constraints:
                continue

            for c in constraints:
                # 约束节点用 (chunk_id + type + value + unit) 作唯一键，避免重复
                constraint_id = f"{chunk_id}_{c['type']}_{c['value']}{c['unit']}"
                session.run("""
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    MERGE (con:Constraint {constraint_id: $cid})
                    SET con.type        = $type,
                        con.value       = $value,
                        con.value_max   = $value_max,
                        con.unit        = $unit,
                        con.description = $description,
                        con.standard    = $standard,
                        con.doc_id      = $doc_id
                    MERGE (sec)-[:HAS_CONSTRAINT]->(con)
                """,
                    chunk_id=chunk_id,
                    cid=constraint_id,
                    type=c["type"],
                    value=c["value"],
                    value_max=c.get("value_max", ""),
                    unit=c["unit"],
                    description=c.get("description", ""),
                    standard=c.get("standard", ""),
                    doc_id=doc_id,
                )
                total += 1

    logger.info("约束写入完成 doc_id=%s constraints=%d", doc_id, total)


def link_image_tools(driver: Driver, image_id: str, tools: list[str]) -> None:
    """将图片分析出的工具链接到 Tool 节点，并建立工具间存在性"""
    if not tools:
        return
    with driver.session() as session:
        session.run("""
            MATCH (i:Image {image_id: $image_id})
            UNWIND $tools AS tool_name
            MERGE (t:Tool {name: tool_name})
            MERGE (i)-[:MENTIONS_TOOL]->(t)
        """, image_id=image_id, tools=[t.strip() for t in tools if t and t.strip()])
