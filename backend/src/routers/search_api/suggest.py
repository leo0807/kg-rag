"""全域语义联想搜索 — 返回文档、章节、实体、推荐问题"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from neo4j import Driver
from ...core.database import get_driver
from ...db.session import get_db
from ...services.storage.es_store import search_sections_es

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/suggest")
async def search_suggest(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
):
    if not q.strip():
        return {"documents": [], "sections": [], "entities": [], "suggested_questions": []}

    # ── 1. ES 检索章节 ─────────────────────────────────────────────
    es_hits = search_sections_es(q, top_k=limit * 2)

    # 去重：先按 doc_id 收集文档
    seen_docs: dict[str, dict] = {}
    sections: list[dict] = []
    for h in es_hits:
        doc_id = h.get("doc_id", "")
        if doc_id and doc_id not in seen_docs:
            seen_docs[doc_id] = {"doc_id": doc_id, "title": h.get("doc_title") or doc_id, "relevance": round(h.get("score", 0), 3)}
        if len(sections) < limit:
            sections.append({
                "chunk_id":  h.get("chunk_id", ""),
                "title":     h.get("title") or h.get("number", ""),
                "doc_id":    doc_id,
                "relevance": round(h.get("score", 0), 3),
            })

    documents = list(seen_docs.values())[:limit]

    # ── 2. Neo4j 实体模糊匹配 ──────────────────────────────────────
    entities: list[dict] = []
    try:
        def _neo4j_entities():
            with driver.session() as s:
                rows = s.run("""
                    MATCH (n) WHERE (n:Tool OR n:Material OR n:Process OR n:Entity)
                      AND n.name CONTAINS $q
                    OPTIONAL MATCH (n)<-[:USES_MATERIAL|REQUIRES_TOOL|HAS_ENTITY]-(sec:Section)
                    RETURN n.name AS name, labels(n)[0] AS type, count(sec) AS mention_count
                    ORDER BY mention_count DESC LIMIT $limit
                """, q=q, limit=limit)
                return [{"name": r["name"], "type": r["type"], "mention_count": r["mention_count"]} for r in rows]

        import asyncio
        entities = await asyncio.to_thread(_neo4j_entities)
    except Exception as e:
        logger.debug("Neo4j entity suggest failed: %s", e)

    # ── 3. 历史问题推荐 ────────────────────────────────────────────
    suggested_questions: list[str] = []
    try:
        result = await db.execute(text("""
            SELECT DISTINCT message->>'content' AS question
            FROM conversations,
                 jsonb_array_elements(messages) AS message
            WHERE message->>'role' = 'user'
              AND message->>'content' ILIKE :pattern
            ORDER BY question
            LIMIT :limit
        """), {"pattern": f"%{q}%", "limit": limit})
        suggested_questions = [r[0] for r in result.all() if r[0]]
    except Exception as e:
        logger.debug("Suggest history query failed: %s", e)

    return {
        "documents":           documents,
        "sections":            sections,
        "entities":            entities,
        "suggested_questions": suggested_questions,
    }
