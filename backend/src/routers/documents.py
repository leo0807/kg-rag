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
        result = session.run("MATCH (n) RETURN count(n) AS total")
        record = result.single()
        return {"node_count": record["total"]}

@router.get("/documents")
async def list_documents(
    page:     int    = 1,
    per_page: int    = 20,
    q:        str    = "",
    driver:   Driver = Depends(get_driver),
):
    skip = (page - 1) * per_page

    with driver.session() as session:
        # 总数
        count_result = session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL
            RETURN count(d) AS total
        """)
        total = count_result.single()["total"]

        # 分页数据
        result = session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL
            OPTIONAL MATCH (d)-[:HAS_SECTION]->(s)
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   d.version     AS version,
                   d.issue_date  AS issue_date,
                   count(s)      AS section_count
            ORDER BY d.name
            SKIP $skip
            LIMIT $per_page
        """, skip=skip, per_page=per_page)

        documents = [dict(r) for r in result]

    return {
        "data":     documents,
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    (total + per_page - 1) // per_page,
    }

@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        # 文档基本信息
        doc_result = session.run("""
            MATCH (d:Document {name: $doc_id})
            RETURN d.name       AS doc_id,
                   d.title      AS title,
                   d.version    AS version,
                   d.issue_date AS issue_date
        """, doc_id=doc_id)
        doc = doc_result.single()

        if not doc:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")

        # 章节列表
        sections_result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.section_number AS number,
                   s.title          AS title,
                   s.chunk_id       AS chunk_id
            ORDER BY s.chunk_id
        """, doc_id=doc_id)
        sections = [dict(r) for r in sections_result]

        # 引用文件
        refs_result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:REFERENCES]->(ref:Document)
            RETURN ref.name AS ref_id
        """, doc_id=doc_id)
        refs = [r["ref_id"] for r in refs_result]

    return {
        **dict(doc),
        "sections": sections,
        "refs":     refs,
    }

@router.get("/sections/{chunk_id}")
async def get_section(
    chunk_id: str,
    driver:   Driver = Depends(get_driver),
):
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Section {chunk_id: $chunk_id})
            RETURN s.section_number AS number,
                   s.title          AS title,
                   s.content        AS content
        """, chunk_id=chunk_id)
        record = result.single()

        if not record:
            from fastapi import HTTPException
            raise HTTPException(404, f"章节不存在: {chunk_id}")

        return dict(record)