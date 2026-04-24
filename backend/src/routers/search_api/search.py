import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

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
        from ...services.storage.es_store import search_sections_es
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
