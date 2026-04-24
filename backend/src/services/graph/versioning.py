"""Document version lineage helpers."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def compute_impact_docs(session, source_ids: list[str]) -> list[str]:
    if not source_ids:
        return []
    result = session.run(
        """
        MATCH (src:Document)
        WHERE src.name IN $sources
        OPTIONAL MATCH (src)<-[:REFERENCES*1..]-(d:Document)
        WHERE d.name IS NOT NULL AND NOT d.name IN $sources
        RETURN collect(DISTINCT d.name) AS impacted
        """,
        sources=source_ids,
    )
    row = result.single()
    impacted = row["impacted"] if row else []
    return sorted({doc for doc in (impacted or []) if doc})


def link_version_lineage(session, doc_id: str, version: str) -> None:
    m = re.match(r"^(.+?)([A-Z])$", doc_id)
    if m:
        base, ver_letter = m.group(1), m.group(2)
    else:
        base = doc_id
        ver_letter = version[:1].upper() if version else ""

    if not ver_letter:
        return

    result = session.run(
        """
        MATCH (old:Document)
        WHERE old.name STARTS WITH $base
          AND old.name <> $doc_id
          AND (
            (old.name =~ $ver_pattern AND substring(old.name, size($base), 1) < $ver_letter)
            OR
            (old.version IS NOT NULL AND old.version < $ver_letter AND old.name = $base)
          )
        RETURN old.name AS old_id
        """,
        base=base,
        doc_id=doc_id,
        ver_pattern=f"^{re.escape(base)}[A-Z]$",
        ver_letter=ver_letter,
    )
    old_ids = [row["old_id"] for row in result]
    if not old_ids:
        return

    for old_id in old_ids:
        session.run(
            """
            MATCH (new_doc:Document {name: $new_id})
            MATCH (old_doc:Document {name: $old_id})
            MERGE (new_doc)-[:SUPERSEDES]->(old_doc)
            MERGE (old_doc)-[:OBSOLETED_BY]->(new_doc)
            """,
            new_id=doc_id,
            old_id=old_id,
        )
        logger.info("版本溯源: %s SUPERSEDES %s", doc_id, old_id)

        session.run(
            """
            MATCH (new_doc:Document {name: $new_id})-[:HAS_SECTION]->(new_sec:Section)
            WHERE NOT EXISTS {
                MATCH (old_doc:Document {name: $old_id})-[:HAS_SECTION]->(old_sec:Section)
                WHERE old_sec.number = new_sec.number
            }
            MERGE (new_doc)-[:ADDED_SECTION]->(new_sec)
            """,
            new_id=doc_id,
            old_id=old_id,
        )
        session.run(
            """
            MATCH (old_doc:Document {name: $old_id})-[:HAS_SECTION]->(old_sec:Section)
            WHERE NOT EXISTS {
                MATCH (new_doc:Document {name: $new_id})-[:HAS_SECTION]->(new_sec:Section)
                WHERE new_sec.number = old_sec.number
            }
            MERGE (old_doc)-[:REMOVED_SECTION]->(old_sec)
            """,
            new_id=doc_id,
            old_id=old_id,
        )
        session.run(
            """
            MATCH (new_doc:Document {name: $new_id})-[:HAS_SECTION]->(new_sec:Section)
            MATCH (old_doc:Document {name: $old_id})-[:HAS_SECTION]->(old_sec:Section)
            WHERE new_sec.number = old_sec.number
              AND new_sec.content <> old_sec.content
            MERGE (old_sec)-[:CHANGED_TO]->(new_sec)
            """,
            new_id=doc_id,
            old_id=old_id,
        )
        logger.info("章节变更检测完成: %s → %s", old_id, doc_id)

    impacted = compute_impact_docs(session, old_ids)
    if impacted:
        session.run(
            """
            MATCH (new_doc:Document {name: $new_id})
            SET new_doc.impact_sources      = $sources,
                new_doc.impact_docs         = $impacted,
                new_doc.impact_count        = $count,
                new_doc.impact_generated_at = timestamp()
            """,
            new_id=doc_id,
            sources=old_ids,
            impacted=impacted,
            count=len(impacted),
        )
        logger.info("变更影响分析: %s 影响 %d 个文档", doc_id, len(impacted))

