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