from __future__ import annotations

import logging
import re as _re

from neo4j import Driver
from .source_meta import _mark_sources

logger = logging.getLogger(__name__)


def apply_entity_aware(
    driver: Driver,
    fused_ids: list[str],
    source_meta: dict[str, dict],
    question: str,
    doc_id: str,
) -> list[str]:
    """Extract entity-matched sections and prepend them to fused_ids."""
    try:
        _terms = list({
            t for t in _re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9][^\s，。；：、！？,.;:!?]{1,7}', question)
            if len(t) >= 2
        })[:20]
        with driver.session() as session:
            entity_result = session.run("""
                UNWIND $terms AS term
                MATCH (e)
                WHERE (e:Tool OR e:Material OR e:Process)
                  AND (e.name = term OR e.name CONTAINS term)
                WITH e LIMIT 10
                MATCH (s:Section)-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->(e)
                WHERE ($doc_id = '' OR s.doc_id = $doc_id)
                RETURN DISTINCT s.chunk_id AS chunk_id
                LIMIT 20
            """, terms=_terms, doc_id=doc_id)
            entity_ids = [r["chunk_id"] for r in entity_result]
            if entity_ids:
                _mark_sources(source_meta, entity_ids, source_type="graph",
                              trace="graph:entity_match", is_graph_expanded=True)
                seen = set(fused_ids)
                fused_ids = [cid for cid in entity_ids if cid not in seen] + fused_ids
    except Exception as e:
        logger.warning("实体感知检索失败: %s", e)
    return fused_ids


def apply_graph_augmented(
    driver: Driver,
    fused_ids: list[str],
    source_meta: dict[str, dict],
    doc_id: str,
) -> list[str]:
    """Expand fused_ids via graph neighborhood and cross-document references."""
    try:
        with driver.session() as session:
            result = session.run("""
                UNWIND $chunk_ids AS cid
                MATCH (s:Section {chunk_id: cid})
                OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION]-(nb:Section)
                WHERE ($doc_id = '' OR nb.doc_id = $doc_id)
                OPTIONAL MATCH (p:Section)-[:HAS_SUBSECTION]->(s)
                WHERE ($doc_id = '' OR p.doc_id = $doc_id)
                OPTIONAL MATCH (s)-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->(e)
                OPTIONAL MATCH (sibling:Section)-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->(e)
                WHERE sibling.chunk_id <> cid AND ($doc_id = '' OR sibling.doc_id = $doc_id)
                WITH collect(DISTINCT s.chunk_id) +
                     collect(DISTINCT nb.chunk_id) +
                     collect(DISTINCT p.chunk_id) +
                     collect(DISTINCT sibling.chunk_id) AS all_ids
                UNWIND all_ids AS id
                WITH id WHERE id IS NOT NULL
                RETURN collect(DISTINCT id) AS expanded_ids
            """, chunk_ids=fused_ids[:5], doc_id=doc_id)
            record = result.single()
            expanded_ids = record["expanded_ids"] if record else []
            _mark_sources(source_meta, expanded_ids, source_type="graph",
                         trace="graph:neighbor_expand", is_graph_expanded=True)
            seen = set(fused_ids)
            for eid in expanded_ids:
                if eid not in seen:
                    fused_ids.append(eid)
                    seen.add(eid)
    except Exception as e:
        logger.warning("图谱增强失败: %s", e)

    if not doc_id:
        try:
            with driver.session() as session:
                ref_result = session.run("""
                    UNWIND $chunk_ids AS cid
                    MATCH (s:Section {chunk_id: cid})<-[:HAS_SECTION]-(d:Document)
                    MATCH (d)-[:REFERENCES]->(ref_doc:Document)
                    MATCH (ref_doc)-[:HAS_SECTION]->(ref_sec:Section)
                    WHERE NOT ref_sec.chunk_id IN $chunk_ids
                    RETURN DISTINCT ref_sec.chunk_id AS chunk_id
                    LIMIT 10
                """, chunk_ids=fused_ids[:5])
                ref_ids = [r["chunk_id"] for r in ref_result]
                _mark_sources(source_meta, ref_ids, source_type="graph",
                             trace="graph:reference_expand", is_graph_expanded=True)
                seen = set(fused_ids)
                for rid in ref_ids:
                    if rid not in seen:
                        fused_ids.append(rid)
                        seen.add(rid)
        except Exception as e:
            logger.warning("跨文档推理失败: %s", e)

    return fused_ids
