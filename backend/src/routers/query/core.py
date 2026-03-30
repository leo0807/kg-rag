"""
检索核心：RRF融合、章节获取、多策略检索
"""
import logging
from neo4j import Driver

logger = logging.getLogger(__name__)


def rrf_fusion(ft_ids: list[str], vec_ids: list[str], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for rank, cid in enumerate(ft_ids,  start=1):
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank)
    for rank, cid in enumerate(vec_ids, start=1):
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def get_section_details(driver: Driver, chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    with driver.session() as session:
        result = session.run("""
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            RETURN s.chunk_id       AS chunk_id,
                   s.doc_id         AS doc_id,
                   s.section_number AS number,
                   s.title          AS title,
                   s.content        AS content
        """, chunk_ids=chunk_ids)
        records = {r["chunk_id"]: dict(r) for r in result}
    return [records[cid] for cid in chunk_ids if cid in records]


def do_retrieval(driver: Driver, question: str, strategy: str, top_k: int):
    """返回 (sections, ft_score_map)"""

    # ES 全文检索
    ft_ids, ft_score_map = [], {}
    try:
        from ...services.es_store import search_sections_es
        es_results   = search_sections_es(question, top_k=top_k * 2)
        ft_ids       = [r["chunk_id"] for r in es_results]
        ft_score_map = {r["chunk_id"]: r["score"] for r in es_results}
    except Exception as e:
        logger.warning("ES 检索失败，降级到 Neo4j: %s", e)
        with driver.session() as session:
            ft_result = session.run("""
                CALL db.index.fulltext.queryNodes('cps_fulltext_index', $q)
                YIELD node, score
                RETURN node.chunk_id AS chunk_id, score
                ORDER BY score DESC LIMIT $top_k
            """, q=question, top_k=top_k * 2)
            rows         = [dict(r) for r in ft_result]
            ft_ids       = [r["chunk_id"] for r in rows]
            ft_score_map = {r["chunk_id"]: r["score"] for r in rows}

    # 向量检索
    vector_ids = []
    if strategy in ("parallel", "graph_augmented"):
        try:
            from ...services.embedder     import embed_query
            from ...services.milvus_store import search_sections
            vector_ids = [r["chunk_id"] for r in search_sections(embed_query(question), top_k=top_k * 2)]
        except Exception as e:
            logger.warning("向量检索失败: %s", e)

    # 策略分发
    if strategy == "parallel" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]
    elif strategy == "sequential":
        fused_ids = list(ft_ids[:top_k])
        if len(fused_ids) < top_k:
            try:
                from ...services.embedder     import embed_query
                from ...services.milvus_store import search_sections
                seen = set(fused_ids)
                for r in search_sections(embed_query(question), top_k=top_k):
                    if r["chunk_id"] not in seen and len(fused_ids) < top_k:
                        fused_ids.append(r["chunk_id"])
                        seen.add(r["chunk_id"])
            except Exception as e:
                logger.warning("串行向量补充失败: %s", e)
    elif strategy == "graph_augmented" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]
    else:
        fused_ids = ft_ids[:top_k * 2]

    # 图谱增强扩展
    if strategy == "graph_augmented" and fused_ids:
        try:
            with driver.session() as session:
                result = session.run("""
                    UNWIND $chunk_ids AS cid
                    MATCH (s:Section {chunk_id: cid})
                    OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION]-(nb:Section)
                    OPTIONAL MATCH (p:Section)-[:HAS_SUBSECTION]->(s)
                    WITH collect(DISTINCT s.chunk_id) +
                         collect(DISTINCT nb.chunk_id) +
                         collect(DISTINCT p.chunk_id) AS all_ids
                    UNWIND all_ids AS id
                    WITH id WHERE id IS NOT NULL
                    RETURN collect(DISTINCT id) AS expanded_ids
                """, chunk_ids=fused_ids[:5])
                record = result.single()
                seen   = set(fused_ids)
                for eid in (record["expanded_ids"] if record else []):
                    if eid not in seen:
                        fused_ids.append(eid)
                        seen.add(eid)
        except Exception as e:
            logger.warning("图谱增强失败: %s", e)

    sections = get_section_details(driver, fused_ids[:top_k * 2])

    if sections and strategy in ("parallel", "graph_augmented"):
        try:
            from ...services.reranker import rerank
            sections = rerank(question, sections, top_k=top_k)
        except Exception as e:
            logger.warning("Reranker 失败: %s", e)

    return sections, ft_score_map