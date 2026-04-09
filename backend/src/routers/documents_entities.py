"""
src/routers/documents_entities.py
文档实体与图片相关 API
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents/{doc_id}/entities")
async def get_document_entities(doc_id: str, driver: Driver = Depends(get_driver)):
    """列出文档中所有工具/材料/工序节点"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            MATCH (s)-[r]->(e)
            WHERE e:Tool OR e:Material OR e:Process
            RETURN DISTINCT
                labels(e)[0]  AS type,
                e.name        AS name,
                type(r)       AS relation,
                s.chunk_id    AS section_chunk_id,
                s.number      AS section_number,
                s.title       AS section_title
            ORDER BY type, name
        """, doc_id=doc_id)
        entities = [dict(r) for r in result]
    return {"doc_id": doc_id, "entities": entities, "total": len(entities)}


@router.get("/entities")
async def search_entities(
    type:   str    = "",
    q:      str    = "",
    driver: Driver = Depends(get_driver),
):
    """实体搜索与过滤。type: Tool|Material|Process，q: 名称关键词"""
    valid_types = {"Tool", "Material", "Process"}
    node_label  = type if type in valid_types else None

    with driver.session() as session:
        if node_label:
            result = session.run(
                f"MATCH (e:{node_label}) "
                "WHERE $q = '' OR toLower(e.name) CONTAINS toLower($q) "
                "RETURN labels(e)[0] AS type, e.name AS name, e.doc_id AS doc_id "
                "ORDER BY e.name LIMIT 100",
                q=q,
            )
        else:
            result = session.run(
                "MATCH (e) WHERE (e:Tool OR e:Material OR e:Process) "
                "AND ($q = '' OR toLower(e.name) CONTAINS toLower($q)) "
                "RETURN labels(e)[0] AS type, e.name AS name, e.doc_id AS doc_id "
                "ORDER BY type, e.name LIMIT 100",
                q=q,
            )
        entities = [dict(r) for r in result]
    return {"entities": entities, "total": len(entities)}


@router.get("/documents/{doc_id}/images")
async def get_document_images(doc_id: str, driver: Driver = Depends(get_driver)):
    """列出文档所有图片及 VLM 描述（含工程图纸专项字段）"""
    import json as _json
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            OPTIONAL MATCH (s)-[:HAS_IMAGE]->(i:Image)
            WHERE i IS NOT NULL
            RETURN i.image_id          AS image_id,
                   i.caption           AS caption,
                   i.path              AS path,
                   i.description       AS description,
                   i.is_drawing        AS is_drawing,
                   i.part_numbers      AS part_numbers,
                   i.annotations       AS annotations,
                   i.assembly_relations AS assembly_relations,
                   i.drawing_summary   AS drawing_summary,
                   s.chunk_id          AS section_chunk_id,
                   s.number            AS section_number,
                   s.title             AS section_title
            ORDER BY s.number
        """, doc_id=doc_id)
        images = []
        for r in result:
            row = dict(r)
            # JSON 字段反序列化
            for field in ("part_numbers", "annotations", "assembly_relations"):
                raw = row.get(field)
                if isinstance(raw, str):
                    try:
                        row[field] = _json.loads(raw)
                    except Exception:
                        row[field] = []
                elif raw is None:
                    row[field] = []
            images.append(row)
    return {"doc_id": doc_id, "images": images, "total": len(images)}


@router.post("/documents/{doc_id}/images/{image_id}/analyze-drawing")
async def analyze_drawing_endpoint(
    doc_id:   str,
    image_id: str,
    driver:   Driver = Depends(get_driver),
):
    """对指定图片发起（重新）工程图纸专项分析，结果写入 Neo4j。"""
    import json as _json

    with driver.session() as session:
        rec = session.run(
            "MATCH (i:Image {image_id: $image_id}) RETURN i.path AS path, i.caption AS caption LIMIT 1",
            image_id=image_id,
        ).single()
    if not rec:
        raise HTTPException(404, f"图片不存在: {image_id}")

    async def _run():
        try:
            from ..services.drawing_analyzer import analyze_drawing
            from ..services.entity_writer    import write_drawing_constraints
            result = analyze_drawing(rec["path"], rec["caption"] or "", doc_id)
            with driver.session() as session:
                session.run("""
                    MATCH (i:Image {image_id: $image_id})
                    SET i.is_drawing         = $is_drawing,
                        i.part_numbers       = $part_numbers,
                        i.annotations        = $annotations,
                        i.assembly_relations = $assembly_relations,
                        i.drawing_summary    = $summary
                """,
                    image_id          = image_id,
                    is_drawing        = result.get("is_drawing", False),
                    part_numbers      = _json.dumps(result.get("part_numbers", []), ensure_ascii=False),
                    annotations       = _json.dumps(result.get("annotations", []), ensure_ascii=False),
                    assembly_relations= _json.dumps(result.get("assembly_relations", []), ensure_ascii=False),
                    summary           = result.get("summary", ""),
                )
            if result.get("annotations"):
                write_drawing_constraints(driver, image_id, doc_id, result["annotations"])
            logger.info("图纸重新分析完成 image_id=%s", image_id)
        except Exception as e:
            logger.warning("图纸重新分析失败 image_id=%s: %s", image_id, e)

    asyncio.create_task(_run())
    return {"image_id": image_id, "status": "analyzing", "message": "图纸分析已在后台启动"}


@router.post("/documents/{doc_id}/reanalyze")
async def reanalyze_document(doc_id: str, driver: Driver = Depends(get_driver)):
    """
    对已入库文档重新提取实体/图片分析（用于模型升级后）。
    实际分析在后台运行，立即返回任务状态。
    """
    with driver.session() as session:
        doc = session.run(
            "MATCH (d:Document {name: $doc_id}) RETURN d LIMIT 1", doc_id=doc_id
        ).single()
        if not doc:
            raise HTTPException(404, f"文档不存在: {doc_id}")

    async def _reanalyze():
        try:
            from ..services.entity_extractor import extract_entities_from_sections
            from ..services.entity_writer    import write_entities
            with driver.session() as session:
                sec_result = session.run("""
                    MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
                    RETURN s.chunk_id AS chunk_id,
                           s.title   AS title,
                           s.content AS content
                """, doc_id=doc_id)
                sections = [dict(r) for r in sec_result]
            if sections:
                entities = extract_entities_from_sections(sections)
                if entities:
                    write_entities(driver, entities, doc_id)
                    logger.info("文档 %s 实体重新提取完成: %d 个", doc_id, len(entities))
        except Exception as e:
            logger.warning("文档 %s 重新分析失败: %s", doc_id, e)

    asyncio.create_task(_reanalyze())
    return {"doc_id": doc_id, "status": "reanalyze_started", "message": "重新分析已在后台启动"}
