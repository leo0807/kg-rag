import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from fastapi import HTTPException
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/stats")
async def stats(driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN 
                count(n) AS total,
                sum(CASE WHEN n:Document AND n.title IS NOT NULL THEN 1 ELSE 0 END) AS documents,
                sum(CASE WHEN n:Section THEN 1 ELSE 0 END) AS sections
        """)
        record = result.single()
        return {
            "total":     record["total"],
            "documents": record["documents"],
            "sections":  record["sections"],
        }

@router.get("/documents")
async def list_documents(
    page:     int    = 1,
    per_page: int    = 20,
    q:        str    = "",
    driver:   Driver = Depends(get_driver),
):
    skip = (page - 1) * per_page

    with driver.session() as session:
        # 搜索条件：匹配 doc_id 或 title
        where_clause = """
            WHERE d.title IS NOT NULL
            AND (
                $q = ''
                OR toLower(d.name)  CONTAINS toLower($q)
                OR toLower(d.title) CONTAINS toLower($q)
            )
        """

        count_result = session.run(f"""
            MATCH (d:Document)
            {where_clause}
            RETURN count(d) AS total
        """, q=q)
        total = count_result.single()["total"]

        result = session.run(f"""
            MATCH (d:Document)
            {where_clause}
            OPTIONAL MATCH (d)-[:HAS_SECTION]->(s)
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   d.version     AS version,
                   d.issue_date  AS issue_date,
                   count(s)      AS section_count
            ORDER BY d.name
            SKIP $skip
            LIMIT $per_page
        """, q=q, skip=skip, per_page=per_page)

        documents = [dict(r) for r in result]

    return {
        "data":     documents,
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    (total + per_page - 1) // per_page,
    }

@router.get("/documents/{doc_id}/pdf-url")
async def get_document_pdf_url(doc_id: str):
    """返回文档原始 PDF 文件的静态访问 URL"""
    from pathlib import Path
    upload_dir = Path("uploads")
    matches = sorted(upload_dir.glob(f"{doc_id}*.pdf")) + sorted(upload_dir.glob(f"{doc_id}*.PDF"))
    if not matches:
        raise HTTPException(404, "PDF 文件未找到，请确认文档已上传")
    filename = matches[0].name
    return {"url": f"/uploads/{filename}", "filename": filename}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        # 文档基本信息
        doc_result = session.run("""
            MATCH (d:Document {name: $doc_id})
            RETURN d.name AS doc_id, d.title AS title,
                   d.version AS version, d.issue_date AS issue_date
        """, doc_id=doc_id)
        doc = doc_result.single()
        if not doc:
            raise HTTPException(404, f"文档不存在: {doc_id}")

        # 章节列表（兼容新字段 number 和旧字段 section_number）
        sec_result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id                               AS chunk_id,
                   COALESCE(s.number, s.section_number, '') AS number,
                   s.title                                  AS title,
                   s.content                                AS content
            ORDER BY COALESCE(s.number, s.section_number, '')
        """, doc_id=doc_id)
        sections = [dict(r) for r in sec_result]

        # 引用文件
        ref_result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:REFERENCES]->(r:Document)
            RETURN r.name AS ref_id
        """, doc_id=doc_id)
        refs = [r["ref_id"] for r in ref_result]

    return {
        "doc_id":    doc["doc_id"],
        "title":     doc["title"]     or "",
        "version":   doc["version"]   or "",
        "issue_date": doc["issue_date"] or "",
        "sections":  sections,
        "refs":      refs,
    }
@router.get("/sections/{chunk_id}")
async def get_section(
    chunk_id: str,
    driver:   Driver = Depends(get_driver),
):
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Section {chunk_id: $chunk_id})
            RETURN COALESCE(s.number, s.section_number, '') AS number,
                   s.title                                  AS title,
                   s.content                                AS content
        """, chunk_id=chunk_id)
        record = result.single()

        if not record:
            from fastapi import HTTPException
            raise HTTPException(404, f"章节不存在: {chunk_id}")

        return dict(record)

@router.get("/search")
async def global_search(
    q:      str,
    top_k:  int    = 10,
    driver: Driver = Depends(get_driver),
):
    """全局全文搜索，跨所有文档搜索章节内容"""
    if not q.strip():
        return {"results": [], "total": 0, "query": q}

    try:
        from ..services.es_store import search_sections_es
        es_results = search_sections_es(q, top_k=top_k, highlight=True)
        results = [
            {
                "chunk_id":  r["chunk_id"],
                "doc_id":    r["doc_id"],
                "number":    r["number"],
                "title":     r["title"],
                "snippet":   "",
                "score":     r["score"],
                "highlight": r.get("highlight", {}),
            }
            for r in es_results
        ]
    except Exception as e:
        logger.warning("ES 搜索失败: %s", e)
        # 降级到 Neo4j 全文检索
        with driver.session() as session:
            result = session.run("""
                CALL db.index.fulltext.queryNodes(
                    'cps_fulltext_index', $q
                ) YIELD node, score
                RETURN node.chunk_id       AS chunk_id,
                       node.doc_id         AS doc_id,
                       node.section_number AS number,
                       node.title          AS title,
                       node.content        AS content,
                       score
                ORDER BY score DESC LIMIT $top_k
            """, q=q, top_k=top_k)
            results = [
                {
                    "chunk_id": r["chunk_id"],
                    "doc_id":   r["doc_id"],
                    "number":   r["number"] or "",
                    "title":    r["title"]  or "",
                    "snippet":  (r["content"] or "")[:200],
                    "score":    round(float(r["score"]), 4),
                    "highlight": {},
                }
                for r in result
            ]

    return {"results": results, "total": len(results), "query": q}

# ── 实体与文档扩展 API ─────────────────────────────────────────────────────────

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
    """列出文档所有图片及 VLM 描述"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            OPTIONAL MATCH (s)-[:HAS_IMAGE]->(i:Image)
            WHERE i IS NOT NULL
            RETURN i.image_id      AS image_id,
                   i.caption       AS caption,
                   i.path          AS path,
                   i.description   AS description,
                   s.chunk_id      AS section_chunk_id,
                   s.number        AS section_number,
                   s.title         AS section_title
            ORDER BY s.number
        """, doc_id=doc_id)
        images = [dict(r) for r in result]
    return {"doc_id": doc_id, "images": images, "total": len(images)}


@router.post("/documents/{doc_id}/reanalyze")
async def reanalyze_document(doc_id: str, driver: Driver = Depends(get_driver)):
    """
    对已入库文档重新提取实体/图片分析（用于模型升级后）。
    实际分析在后台运行，立即返回任务状态。
    """
    import asyncio

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
