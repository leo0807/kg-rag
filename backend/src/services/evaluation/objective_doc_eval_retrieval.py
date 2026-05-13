from __future__ import annotations

from typing import Any

from neo4j import Driver

from .objective_doc_eval_metrics import (
    _collect_objective_terms,
    _merge_unique_sections,
    _score_objective_section,
)
from .objective_doc_eval_parser import _build_objective_retrieval_query

_DO_RETRIEVAL: Any | None = None


def _get_do_retrieval():
    global _DO_RETRIEVAL
    if callable(_DO_RETRIEVAL):
        return _DO_RETRIEVAL
    from ...routers.query.core import do_retrieval

    _DO_RETRIEVAL = do_retrieval
    return do_retrieval


def _expand_graph_neighbors(driver: Driver, seed_sections: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    chunk_ids = [s.get("chunk_id") for s in seed_sections if s.get("chunk_id")]
    if not chunk_ids:
        return []
    with driver.session() as session:
        result = session.run(
            """
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION]-(nb:Section)
            OPTIONAL MATCH (p:Section)-[:HAS_SUBSECTION]->(s)
            WITH collect(DISTINCT nb) + collect(DISTINCT p) AS related
            UNWIND related AS sec
            WITH DISTINCT sec WHERE sec IS NOT NULL
            RETURN sec.chunk_id AS chunk_id, sec.doc_id AS doc_id, sec.number AS number,
                   sec.title AS title, sec.content AS content, sec.page_idx AS page_idx,
                   sec.bbox AS bbox, sec.seq_index AS seq_index
            LIMIT $limit
            """,
            chunk_ids=chunk_ids[:6],
            limit=limit,
        )
        return [dict(row) for row in result]


def _expand_local_neighbors(driver: Driver, seed_sections: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    chunk_ids = [s.get("chunk_id") for s in seed_sections if s.get("chunk_id")]
    if not chunk_ids:
        return []
    with driver.session() as session:
        result = session.run(
            """
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            MATCH (nb:Section {doc_id: s.doc_id})
            WHERE nb.chunk_id <> s.chunk_id
              AND nb.seq_index IS NOT NULL AND s.seq_index IS NOT NULL
              AND abs(nb.seq_index - s.seq_index) <= 2
            RETURN DISTINCT nb.chunk_id AS chunk_id, nb.doc_id AS doc_id, nb.number AS number,
                            nb.title AS title, nb.content AS content, nb.page_idx AS page_idx,
                            nb.bbox AS bbox, nb.seq_index AS seq_index
            LIMIT $limit
            """,
            chunk_ids=chunk_ids[:6],
            limit=limit,
        )
        return [dict(row) for row in result]


def retrieve_objective_sections(
    question: str,
    options: list[dict[str, str]],
    strategy: str,
    top_k: int,
    driver: Driver,
    doc_id: str = "",
    allow_fallback: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    do_retrieval = _get_do_retrieval()
    candidate_k = max(top_k * 4, 12)
    stem_query = _build_objective_retrieval_query(question, [])
    merged_sections: list[dict[str, Any]] = []
    ft_score_map: dict[str, float] = {}

    retrieval_plans = [(stem_query, strategy, False, 0.5)]
    if strategy != "graph_augmented":
        retrieval_plans.append((stem_query, "graph_augmented", False, 0.5))

    for query, plan_strategy, use_hyde, hyde_alpha in retrieval_plans:
        sections, local_scores, _ = do_retrieval(
            driver,
            query,
            plan_strategy,
            candidate_k,
            use_hyde=use_hyde,
            hyde_alpha=hyde_alpha,
            doc_id=doc_id,
        )
        merged_sections = _merge_unique_sections(merged_sections, sections)
        for chunk_id, score in local_scores.items():
            ft_score_map[chunk_id] = max(ft_score_map.get(chunk_id, float("-inf")), score)

    if allow_fallback and doc_id and not merged_sections:
        for query, plan_strategy, use_hyde, hyde_alpha in retrieval_plans:
            sections, local_scores, _ = do_retrieval(
                driver,
                query,
                plan_strategy,
                candidate_k,
                use_hyde=use_hyde,
                hyde_alpha=hyde_alpha,
            )
            merged_sections = _merge_unique_sections(merged_sections, sections)
            for chunk_id, score in local_scores.items():
                ft_score_map[chunk_id] = max(ft_score_map.get(chunk_id, float("-inf")), score)

    merged_sections = _merge_unique_sections(
        merged_sections,
        _expand_graph_neighbors(driver, merged_sections),
        _expand_local_neighbors(driver, merged_sections),
    )
    terms = _collect_objective_terms(question, options)
    doc_density: dict[str, int] = {}
    for section in merged_sections[:candidate_k]:
        section_doc_id = section.get("doc_id", "")
        if section_doc_id:
            doc_density[section_doc_id] = doc_density.get(section_doc_id, 0) + 1

    ranked = sorted(
        merged_sections,
        key=lambda s: _score_objective_section(s, terms, ft_score_map, doc_density),
        reverse=True,
    )
    return ranked[: max(top_k * 2, 8)], ft_score_map
