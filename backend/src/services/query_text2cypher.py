from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .answer_humanizer import humanize_answer_text

if TYPE_CHECKING:
    from neo4j import Driver

_DOC_ID_RE = re.compile(r"(?i)CPS\d{3,4}")
_TOTAL_HINTS = ("多少", "几本", "总共", "一共", "共有", "总数", "数量")
_SECTION_HINTS = ("章节", "章节数", "几章", "多少章", "多少个章节", "多少章节")
_IMAGE_HINTS = ("图片", "图示", "插图", "图")
_TABLE_HINTS = ("表格", "表", "多少个表")


def _extract_doc_id(question: str) -> str | None:
    m = _DOC_ID_RE.search(question or "")
    return m.group(0).upper() if m else None


def _has_any(question: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in question for keyword in keywords)


def _count_total_docs(driver: Driver) -> int:
    with driver.session() as session:
        record = session.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN count(d) AS cnt"
        ).single()
    return int(record["cnt"] if record and record["cnt"] is not None else 0)


def _count_doc_sections(driver: Driver, doc_id: str) -> int:
    with driver.session() as session:
        record = session.run(
            """
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN count(s) AS cnt
            """,
            doc_id=doc_id,
        ).single()
    return int(record["cnt"] if record and record["cnt"] is not None else 0)


def _count_doc_images(driver: Driver, doc_id: str) -> int:
    with driver.session() as session:
        record = session.run(
            """
            MATCH (d:Document {name: $doc_id})-[:HAS_IMAGE]->(i:Image)
            RETURN count(i) AS cnt
            """,
            doc_id=doc_id,
        ).single()
    return int(record["cnt"] if record and record["cnt"] is not None else 0)


def _count_doc_tables(driver: Driver, doc_id: str) -> int:
    with driver.session() as session:
        record = session.run(
            """
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(:Section)-[:HAS_TABLE]->(t:Table)
            RETURN count(DISTINCT t) AS cnt
            """,
            doc_id=doc_id,
        ).single()
    return int(record["cnt"] if record and record["cnt"] is not None else 0)


def resolve_count_question(question: str | None, driver: Driver) -> dict | None:
    q = (question or "").strip()
    if not q:
        return None

    has_count_hint = _has_any(q, _TOTAL_HINTS + _SECTION_HINTS + _IMAGE_HINTS + _TABLE_HINTS)
    doc_id = _extract_doc_id(q)

    if not has_count_hint:
        return None

    if not doc_id and ("CPS" in q.upper() or "文档" in q):
        count = _count_total_docs(driver)
        answer = humanize_answer_text(f"系统里共有 {count} 本 CPS 文档。", q)
        return {
            "kind": "total_docs",
            "answer": answer,
            "count": count,
            "cypher": "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN count(d) AS cnt",
            "label": "CPS 文档总数",
        }

    if not doc_id:
        return None

    if _has_any(q, _IMAGE_HINTS):
        count = _count_doc_images(driver, doc_id)
        answer = humanize_answer_text(f"{doc_id} 共 {count} 张图片。", q)
        return {
            "kind": "image_count",
            "doc_id": doc_id,
            "answer": answer,
            "count": count,
            "cypher": "MATCH (d:Document {name: $doc_id})-[:HAS_IMAGE]->(i:Image) RETURN count(i) AS cnt",
            "label": "图片数",
        }

    if _has_any(q, _TABLE_HINTS):
        count = _count_doc_tables(driver, doc_id)
        answer = humanize_answer_text(f"{doc_id} 共 {count} 个表格。", q)
        return {
            "kind": "table_count",
            "doc_id": doc_id,
            "answer": answer,
            "count": count,
            "cypher": "MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(:Section)-[:HAS_TABLE]->(t:Table) RETURN count(DISTINCT t) AS cnt",
            "label": "表格数",
        }

    # 默认按章节数回答，覆盖“有多少个章节/多少章节/章节数”等问法
    if _has_any(q, _SECTION_HINTS) or has_count_hint:
        count = _count_doc_sections(driver, doc_id)
        answer = humanize_answer_text(f"{doc_id} 共 {count} 个章节。", q)
        return {
            "kind": "section_count",
            "doc_id": doc_id,
            "answer": answer,
            "count": count,
            "cypher": "MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section) RETURN count(s) AS cnt",
            "label": "章节数",
        }

    return None
