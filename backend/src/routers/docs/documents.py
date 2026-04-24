import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver
from ...auth.deps import get_current_user, get_protected_driver
from ...core.database import get_driver
from ...db.models import User
try:
    from ...core.cache import get_redis
except ImportError:
    def get_redis():  # type: ignore[misc]
        raise RuntimeError("cache not available")
import json as _json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/stats")
async def stats(driver: Driver = Depends(get_driver)):
    try:
        r = get_redis()
        cached = r.get("neo4j:stats")
        if cached:
            return _json.loads(cached)
    except Exception:
        r = None
    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN
                count(n) AS total,
                sum(CASE WHEN n:Document AND n.title IS NOT NULL THEN 1 ELSE 0 END) AS documents,
                sum(CASE WHEN n:Section THEN 1 ELSE 0 END) AS sections
        """)
        record = result.single()
        data = {"total": record["total"], "documents": record["documents"], "sections": record["sections"]}
    try:
        if r: r.setex("neo4j:stats", 60, _json.dumps(data))
    except Exception:
        pass
    return data

@router.get("/documents")
async def list_documents(
    page:     int    = 1,
    per_page: int    = 20,
    q:        str    = "",
    _:        User   = Depends(get_current_user),
    driver:   Driver = Depends(get_protected_driver),
):
    cache_key = f"docs:{page}:{per_page}:{q}"
    _rc = None
    try:
        _rc = get_redis()
        cached = _rc.get(cache_key)
        if cached:
            return _json.loads(cached)
    except Exception:
        pass
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
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   d.version     AS version,
                   d.issue_date  AS issue_date,
                   size([(d)-[:HAS_SECTION]->(s) | s]) AS section_count,
                   size([(d)-[:HAS_IMAGE]->(i:Image) | i]) AS image_count,
                   size([(d)-[:HAS_IMAGE]->(i:Image)
                         WHERE i.analysis_level IN ['full', 'basic'] | i]) AS analyzed_image_count
            ORDER BY d.name
            SKIP $skip
            LIMIT $per_page
        """, q=q, skip=skip, per_page=per_page)

        def _analysis_status(img_count: int, analyzed: int) -> str:
            if img_count == 0:
                return "none"
            if analyzed >= img_count:
                return "analyzed"
            if analyzed > 0:
                return "partial"
            return "pending"

        documents = []
        for r in result:
            row = dict(r)
            row["analysis_status"] = _analysis_status(
                row.get("image_count", 0),
                row.get("analyzed_image_count", 0),
            )
            documents.append(row)

    out = {"data": documents, "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page}
    try:
        if _rc: _rc.setex(cache_key, 30, _json.dumps(out, default=str))
    except Exception:
        pass
    return out

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
                   s.content                                AS content,
                   s.page_idx                               AS page_idx,
                   s.bbox                                   AS bbox
        """, doc_id=doc_id)
        # 自然排序：按 number 字段的各级数字排序（处理 "10" > "9" 和 "6.1.8" 多级）
        def _section_sort_key(row: dict):
            num = row.get("number") or ""
            try:
                return [int(p) for p in num.split(".") if p.isdigit() or (p.lstrip("-").isdigit())]
            except Exception:
                return [0]
        sections = sorted([dict(r) for r in sec_result], key=_section_sort_key)

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
