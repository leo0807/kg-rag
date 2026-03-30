"""
src/services/entity_writer.py
将工具、材料、工序节点写入 Neo4j 知识图谱

节点类型：
  Tool     (:Tool {name})          工具/设备
  Material (:Material {name})      材料/耗材
  Process  (:Process {name})       工序/操作步骤

关系：
  (Section)-[:REQUIRES_TOOL]->(:Tool)
  (Section)-[:USES_MATERIAL]->(:Material)
  (Section)-[:INVOLVES_PROCESS]->(:Process)
  (Image)-[:MENTIONS_TOOL]->(:Tool)
"""
import logging
from neo4j import Driver

logger = logging.getLogger(__name__)


def write_entities(driver: Driver, doc_id: str, entity_data: list[dict]) -> None:
    """
    entity_data: [{"chunk_id", "tools": [...], "materials": [...], "processes": [...]}]
    """
    tools_total = materials_total = processes_total = 0

    with driver.session() as session:
        for item in entity_data:
            chunk_id  = item.get("chunk_id", "")
            tools     = [t.strip() for t in item.get("tools", [])     if t and t.strip()]
            materials = [m.strip() for m in item.get("materials", []) if m and m.strip()]
            processes = [p.strip() for p in item.get("processes", []) if p and p.strip()]

            if tools:
                session.run("""
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $tools AS tool_name
                    MERGE (t:Tool {name: tool_name})
                    SET t.doc_id = $doc_id
                    MERGE (sec)-[:REQUIRES_TOOL]->(t)
                """, chunk_id=chunk_id, tools=tools, doc_id=doc_id)
                tools_total += len(tools)

            if materials:
                session.run("""
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $materials AS mat_name
                    MERGE (m:Material {name: mat_name})
                    SET m.doc_id = $doc_id
                    MERGE (sec)-[:USES_MATERIAL]->(m)
                """, chunk_id=chunk_id, materials=materials, doc_id=doc_id)
                materials_total += len(materials)

            if processes:
                session.run("""
                    MATCH (sec:Section {chunk_id: $chunk_id})
                    UNWIND $processes AS proc_name
                    MERGE (p:Process {name: proc_name})
                    SET p.doc_id = $doc_id
                    MERGE (sec)-[:INVOLVES_PROCESS]->(p)
                """, chunk_id=chunk_id, processes=processes, doc_id=doc_id)
                processes_total += len(processes)

    logger.info(
        "实体写入完成 doc_id=%s tools=%d materials=%d processes=%d",
        doc_id, tools_total, materials_total, processes_total,
    )


def link_image_tools(driver: Driver, image_id: str, tools: list[str]) -> None:
    """将图片分析出的工具链接到 Tool 节点"""
    if not tools:
        return
    with driver.session() as session:
        session.run("""
            MATCH (i:Image {image_id: $image_id})
            UNWIND $tools AS tool_name
            MERGE (t:Tool {name: tool_name})
            MERGE (i)-[:MENTIONS_TOOL]->(t)
        """, image_id=image_id, tools=tools)
