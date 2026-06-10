"""
规范百科 Wiki API — 基于 Neo4j 图谱返回结构化规范知识卡片
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, get_optional_user
from ..core.database import get_driver
from ..db.models import User
from ..db.session import get_db
from ..services.qa.term_linker import _TERM_DICT, extract_links

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/wiki", tags=["wiki"])


def _run_cypher(query: str, params: dict | None = None) -> list[dict]:
    driver = get_driver()
    if not driver:
        return []
    try:
        with driver.session() as sess:
            result = sess.run(query, params or {})
            return [dict(r) for r in result]
    except Exception as e:
        logger.warning("wiki cypher error: %s", e)
        return []


@router.get("/index")
async def wiki_index(
    _user: User | None = Depends(get_optional_user),
):
    """返回所有规范文档的简要列表。"""
    rows = _run_cypher("""
        MATCH (d:Document)
        OPTIONAL MATCH (d)-[:HAS_SECTION]->(s:Section)
        WITH d, count(s) AS section_count
        RETURN d.name AS doc_id,
               d.title AS title,
               d.spec_type AS spec_type,
               section_count
        ORDER BY d.name
        LIMIT 200
    """)
    return [
        {
            "doc_id":        r.get("doc_id", ""),
            "title":         r.get("title") or r.get("doc_id", ""),
            "spec_type":     r.get("spec_type", ""),
            "section_count": r.get("section_count", 0),
        }
        for r in rows
    ]


@router.get("/terms")
async def wiki_terms(_user: User | None = Depends(get_optional_user)):
    """返回内置术语词典列表。"""
    return [{"term": k, "definition": v} for k, v in _TERM_DICT.items()]


@router.get("/term/{term}")
async def get_term(
    term: str,
    _user: User | None = Depends(get_optional_user),
):
    definition = _TERM_DICT.get(term)
    if not definition:
        raise HTTPException(404, "术语不存在")
    return {"term": term, "definition": definition}


@router.get("/{doc_id}")
async def wiki_card(
    doc_id: str,
    _user: User | None = Depends(get_optional_user),
):
    """返回规范知识卡片。"""
    doc_id = doc_id.upper()

    doc_rows = _run_cypher(
        "MATCH (d:Document {name: $doc_id}) RETURN d LIMIT 1",
        {"doc_id": doc_id},
    )
    if not doc_rows:
        raise HTTPException(404, f"规范 {doc_id} 不存在")

    doc = doc_rows[0].get("d", {})

    # scope section
    scope_rows = _run_cypher("""
        MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
        WHERE toLower(s.title) CONTAINS '范围' OR s.section_number = '1'
        RETURN s.content AS content LIMIT 1
    """, {"doc_id": doc_id})
    scope = (scope_rows[0].get("content") or "")[:500] if scope_rows else ""

    # key terms
    term_rows = _run_cypher("""
        MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
        WHERE toLower(s.title) CONTAINS '术语'
        RETURN s.content AS content LIMIT 1
    """, {"doc_id": doc_id})
    raw_terms = (term_rows[0].get("content") or "") if term_rows else ""

    # related docs via citations
    ref_rows = _run_cypher("""
        MATCH (d:Document {name: $doc_id})-[:CITES]->(r:Document)
        RETURN r.name AS doc_id, r.title AS title LIMIT 10
    """, {"doc_id": doc_id})

    # main processes
    proc_rows = _run_cypher("""
        MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
        WHERE toLower(s.title) CONTAINS '工艺' OR toLower(s.title) CONTAINS '规程'
        RETURN s.title AS title, s.content AS content LIMIT 3
    """, {"doc_id": doc_id})

    # key numbers / materials via entity nodes
    mat_rows = _run_cypher("""
        MATCH (d:Document {name: $doc_id})-[:MENTIONS]->(e:Entity)
        WHERE e.type IN ['material', 'substance', 'chemical']
        RETURN DISTINCT e.name AS name LIMIT 10
    """, {"doc_id": doc_id})

    return {
        "doc_id":          doc_id,
        "title":           doc.get("title") or doc_id,
        "spec_type":       doc.get("spec_type", ""),
        "summary":         doc.get("summary", "") or scope[:200],
        "scope":           scope,
        "key_terms":       _extract_term_lines(raw_terms),
        "related_specs":   [{"doc_id": r.get("doc_id"), "title": r.get("title")} for r in ref_rows],
        "main_processes":  [{"title": r.get("title"), "summary": (r.get("content") or "")[:200]} for r in proc_rows],
        "involved_materials": [r.get("name") for r in mat_rows if r.get("name")],
    }


@router.get("/links/extract")
async def extract_text_links(
    text: str = Query(..., max_length=2000),
    _user: User | None = Depends(get_optional_user),
):
    """提取文本中的术语和规范链接（前端调用）。"""
    links = extract_links(text)
    return [
        {"start": l.start, "end": l.end, "text": l.text,
         "kind": l.kind, "href": l.href, "tooltip": l.tooltip}
        for l in links
    ]


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_term_lines(raw: str) -> list[dict]:
    import re
    results = []
    for m in re.finditer(r'(\d+\.\d+)\s+([^\n（(]+)[（(]([^\n）)]+)[）)]?', raw):
        results.append({"term": m.group(2).strip(), "definition": m.group(3).strip()})
    return results[:10]
