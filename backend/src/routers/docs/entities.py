"""
文档实体 API（实体搜索、文档实体列表、表格约束、重新分析）
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from ...core.database import get_driver

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
    type:     str    = "",
    q:        str    = "",
    page:     int    = 1,
    per_page: int    = 50,
    driver:   Driver = Depends(get_driver),
):
    """实体搜索与过滤，支持分页。type: Tool|Material|Process，q: 名称关键词"""
    valid_types = {"Tool", "Material", "Process"}
    node_label  = type if type in valid_types else None
    per_page    = min(max(per_page, 1), 200)
    skip        = (page - 1) * per_page

    with driver.session() as session:
        if node_label:
            q_where = "($q = '' OR toLower(e.name) CONTAINS toLower($q))"
            cnt = session.run(
                f"MATCH (e:{node_label}) WHERE {q_where} RETURN count(e) AS total", q=q
            ).single()
            total = cnt["total"] if cnt else 0
            result = session.run(
                f"MATCH (e:{node_label}) WHERE {q_where} "
                "RETURN labels(e)[0] AS type, e.name AS name, e.doc_id AS doc_id "
                "ORDER BY e.name SKIP $skip LIMIT $per_page",
                q=q, skip=skip, per_page=per_page,
            )
        else:
            q_where = "(e:Tool OR e:Material OR e:Process) AND ($q = '' OR toLower(e.name) CONTAINS toLower($q))"
            cnt = session.run(f"MATCH (e) WHERE {q_where} RETURN count(e) AS total", q=q).single()
            total = cnt["total"] if cnt else 0
            result = session.run(
                f"MATCH (e) WHERE {q_where} "
                "RETURN labels(e)[0] AS type, e.name AS name, e.doc_id AS doc_id "
                "ORDER BY labels(e)[0], e.name SKIP $skip LIMIT $per_page",
                q=q, skip=skip, per_page=per_page,
            )
        entities = [dict(r) for r in result]
    return {
        "entities": entities, "total": total, "page": page,
        "per_page": per_page, "pages": max(1, -(-total // per_page)),
    }


@router.post("/documents/{doc_id}/reanalyze")
async def reanalyze_document(doc_id: str, driver: Driver = Depends(get_driver)):
    """对已入库文档重新提取实体（后台运行）。"""
    with driver.session() as session:
        if not session.run("MATCH (d:Document {name: $doc_id}) RETURN d LIMIT 1", doc_id=doc_id).single():
            raise HTTPException(404, f"文档不存在: {doc_id}")

    async def _reanalyze():
        try:
            from ...services.graph.entity_extractor import extract_entities_from_sections
            from ...services.graph.entity_writer    import reset_document_entity_graph, write_entities
            with driver.session() as session:
                sections = [dict(r) for r in session.run("""
                    MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
                    RETURN s.chunk_id AS chunk_id, s.title AS title, s.content AS content
                """, doc_id=doc_id)]
            if sections:
                reset_document_entity_graph(driver, doc_id)
                entities = extract_entities_from_sections(sections)
                if entities:
                    write_entities(driver, doc_id, entities)
                    logger.info("文档 %s 实体重新提取完成: %d 个", doc_id, len(entities))
        except Exception as e:
            logger.warning("文档 %s 重新分析失败: %s", doc_id, e)

    asyncio.create_task(_reanalyze())
    return {"doc_id": doc_id, "status": "reanalyze_started", "message": "重新分析已在后台启动"}


@router.get("/documents/{doc_id}/tables")
async def get_document_tables(doc_id: str, driver: Driver = Depends(get_driver)):
    """查询从表格中提取的约束节点（source='table'）"""
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Section {doc_id: $doc_id})-[:HAS_CONSTRAINT]->(c:Constraint {source: 'table'})
            RETURN c.constraint_id AS constraint_id,
                   c.type         AS type,
                   c.description  AS description,
                   c.value        AS value,
                   c.value_min    AS value_min,
                   c.value_max    AS value_max,
                   c.unit         AS unit,
                   s.chunk_id     AS chunk_id,
                   s.number       AS section_number,
                   s.title        AS section_title
            ORDER BY s.number, c.type
        """, doc_id=doc_id)
        constraints = [dict(r) for r in result]
    return {"doc_id": doc_id, "constraints": constraints, "total": len(constraints)}
