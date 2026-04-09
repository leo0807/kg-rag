"""
缺陷节点写入器 — 将检测到的缺陷写入 Neo4j 图谱

图谱模式:
    (Defect)-[:DETECTED_IN]->(Image)
    (Defect)-[:RELATED_TO]->(Process)   # 关联相关工序
    (Defect)-[:AFFECTS]->(Material)     # 关联受影响材料
    (Hazard)-[:WARNS_ABOUT]->(Defect)   # 已有 Hazard 节点关联
"""
import json
import logging
import uuid

logger = logging.getLogger(__name__)


def write_defect(
    driver,
    image_id:  str,
    doc_id:    str,
    defect:    dict,
) -> str:
    """
    写入单条缺陷记录，返回 defect_id。

    defect dict keys: defect_type, label, confidence, bbox, description (optional)
    """
    defect_id = f"defect_{image_id}_{defect['defect_type']}_{uuid.uuid4().hex[:8]}"
    with driver.session() as session:
        session.run("""
            MERGE (d:Defect {defect_id: $defect_id})
            SET d.type        = $defect_type,
                d.label       = $label,
                d.confidence  = $confidence,
                d.bbox        = $bbox,
                d.description = $description,
                d.doc_id      = $doc_id,
                d.image_id    = $image_id
            WITH d
            MATCH (i:Image {image_id: $image_id})
            MERGE (d)-[:DETECTED_IN]->(i)
        """,
            defect_id   = defect_id,
            defect_type = defect.get("defect_type", "unknown"),
            label       = defect.get("label", ""),
            confidence  = defect.get("confidence", 0.0),
            bbox        = json.dumps(defect.get("bbox", []), ensure_ascii=False),
            description = defect.get("description", ""),
            doc_id      = doc_id,
            image_id    = image_id,
        )
    return defect_id


def link_defect_to_process(driver, defect_id: str, process_names: list[str]):
    """将缺陷与相关工序节点关联"""
    if not process_names:
        return
    with driver.session() as session:
        session.run("""
            MATCH (d:Defect {defect_id: $defect_id})
            UNWIND $names AS name
            MATCH (p:Process {name: name})
            MERGE (d)-[:RELATED_TO]->(p)
        """, defect_id=defect_id, names=process_names)


def query_hazard_remediation(driver, defect_type: str, doc_id: str = "") -> list[dict]:
    """
    查询图谱中与该缺陷类型对应的 Hazard 节点，返回整改建议。

    查询策略:
    1. 精确匹配 Hazard.type 或 Hazard.label 包含 defect_type 关键字
    2. 通过 Process 节点间接关联
    """
    results = []
    with driver.session() as session:
        # 直接 Hazard 匹配
        r1 = session.run("""
            MATCH (h:Hazard)
            WHERE toLower(h.type) CONTAINS toLower($kw)
               OR toLower(h.label) CONTAINS toLower($kw)
               OR toLower(h.description) CONTAINS toLower($kw)
            RETURN h.hazard_id   AS hazard_id,
                   h.label       AS label,
                   h.description AS description,
                   h.remediation AS remediation,
                   h.standard    AS standard
            LIMIT 5
        """, kw=defect_type)
        results.extend([dict(r) for r in r1])

        # 通过 Process 关联（Hazard -> Process -> Defect 语义匹配）
        if not results:
            r2 = session.run("""
                MATCH (h:Hazard)-[:ASSOCIATED_WITH|WARNS_ABOUT]->(p:Process)
                WHERE toLower(p.name) CONTAINS toLower($kw)
                RETURN h.hazard_id   AS hazard_id,
                       h.label       AS label,
                       h.description AS description,
                       h.remediation AS remediation,
                       h.standard    AS standard
                LIMIT 5
            """, kw=defect_type)
            results.extend([dict(r) for r in r2])

    return results


def write_defects_batch(
    driver,
    image_id: str,
    doc_id:   str,
    defects:  list[dict],
) -> list[str]:
    """批量写入缺陷，返回所有 defect_id 列表"""
    ids = []
    for defect in defects:
        try:
            did = write_defect(driver, image_id, doc_id, defect)
            ids.append(did)
        except Exception as e:
            logger.warning("缺陷写入失败 image_id=%s type=%s: %s",
                           image_id, defect.get("defect_type"), e)
    return ids
