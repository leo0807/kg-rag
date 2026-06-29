from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from ...services.infra.health import health_monitor

# 持久线程池：避免每次检索都创建/销毁线程（每次约 1-3ms 开销）
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="parallel_search")

logger = logging.getLogger(__name__)


def search_fulltext_and_vector(
    driver,
    question: str,
    top_k: int,
    use_hyde: bool = False,
    hyde_alpha: float = 0.5,
    doc_id: str = "",
):
    from .embedder import embed_query, get_cached_embedding
    from .hyde_service import get_hyde_service
    from .query_expander import expand_query
    from ...services.storage.es_store import search_sections_es
    from ...services.storage.milvus_store import search_sections

    t0 = time.time()
    search_query, expansion_info = expand_query(driver, question)
    logger.info("[timing] 查询扩展 %.2fs", time.time() - t0)

    def _search_fulltext():
        t_ft = time.time()
        ft_ids: list[str] = []
        ft_score_map: dict[str, float] = {}
        if health_monitor.elasticsearch.is_ok:
            try:
                es_results = search_sections_es(search_query, top_k=top_k * 2, doc_id=doc_id)
                ft_ids = [r["chunk_id"] for r in es_results]
                ft_score_map = {r["chunk_id"]: r["score"] for r in es_results}
            except Exception as exc:
                logger.warning("ES 检索失败，降级到 Neo4j 全文索引: %s", exc)
                health_monitor.elasticsearch.state = health_monitor.elasticsearch.state.__class__.DOWN
        if not ft_ids and health_monitor.neo4j.is_ok:
            try:
                with driver.session() as session:
                    ft_result = session.run("""
                        CALL db.index.fulltext.queryNodes('cps_fulltext_index', $q)
                        YIELD node, score
                        WHERE ($doc_id = '' OR node.doc_id = $doc_id)
                        RETURN node.chunk_id AS chunk_id, score
                        ORDER BY score DESC LIMIT $top_k
                    """, q=search_query, top_k=top_k * 2, doc_id=doc_id)
                    rows = [dict(r) for r in ft_result]
                    ft_ids = [r["chunk_id"] for r in rows]
                    ft_score_map = {r["chunk_id"]: r["score"] for r in rows}
            except Exception as exc:
                logger.warning("Neo4j 全文索引检索也失败: %s", exc)
        logger.info("[timing] 全文检索 %.2fs", time.time() - t_ft)
        return ft_ids, ft_score_map

    def _search_vector():
        t_vec = time.time()
        if not health_monitor.milvus.is_ok:
            logger.info("Milvus 不可用（已知 DOWN），跳过向量检索")
            return []
        try:
            t_emb = time.time()
            query_vec = (
                get_hyde_service().hybrid_embedding(question, alpha=hyde_alpha)
                if use_hyde
                else list(get_cached_embedding(question))
            )
            logger.info("[timing] 向量化 %.2fs", time.time() - t_emb)
            t_search = time.time()
            return [r["chunk_id"] for r in search_sections(query_vec, top_k=top_k * 2, doc_id=doc_id)]
        except Exception as exc:
            logger.warning("向量检索失败: %s", exc)
            return []
        finally:
            logger.info("[timing] 向量检索 %.2fs", time.time() - t_vec)

    ft_future = _POOL.submit(_search_fulltext)
    vec_future = _POOL.submit(_search_vector)
    ft_ids, ft_score_map = ft_future.result()
    vector_ids = vec_future.result()

    logger.info("[timing] parallel_search 总耗时 %.2fs", time.time() - t0)
    return search_query, expansion_info, ft_ids, ft_score_map, vector_ids
