"""
检索核心：RRF融合、章节获取、多策略检索

策略列表:
  parallel        — 全文 + 向量 RRF 融合
  sequential      — 全文优先，不足时向量补充
  graph_augmented — parallel + 图谱邻居扩展 + 跨文档推理
  gnn             — GNN 结构感知嵌入 + 全文 RRF 融合（GraphSAGE）
  multi_hop       — 多跳推理 Agent（独立模块）
"""
import logging
from neo4j import Driver
from ...services.health import health_monitor

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
            RETURN s.chunk_id AS chunk_id,
                   s.doc_id   AS doc_id,
                   s.number   AS number,
                   s.title    AS title,
                   s.content  AS content,
                   s.page_idx AS page_idx,
                   s.bbox     AS bbox
        """, chunk_ids=chunk_ids)
        records = {r["chunk_id"]: dict(r) for r in result}
    return [records[cid] for cid in chunk_ids if cid in records]


def do_retrieval(driver: Driver, question: str, strategy: str, top_k: int):
    """返回 (sections, ft_score_map)"""

    # 0. 查询扩展（近义词）
    from ...services.query_expander import expand_query
    search_query = expand_query(driver, question)

    # ES 全文检索
    ft_ids, ft_score_map = [], {}
    if health_monitor.elasticsearch.is_ok:
        try:
            from ...services.es_store import search_sections_es
            es_results   = search_sections_es(search_query, top_k=top_k * 2)
            ft_ids       = [r["chunk_id"] for r in es_results]
            ft_score_map = {r["chunk_id"]: r["score"] for r in es_results}
        except Exception as e:
            logger.warning("ES 检索失败，降级到 Neo4j 全文索引: %s", e)
            health_monitor.elasticsearch.state = health_monitor.elasticsearch.state.__class__.DOWN
    else:
        logger.info("ES 不可用（已知 DOWN），跳过 ES 检索")

    # ES 不可用时降级到 Neo4j 全文索引
    if not ft_ids and health_monitor.neo4j.is_ok:
        try:
            with driver.session() as session:
                ft_result = session.run("""
                    CALL db.index.fulltext.queryNodes('cps_fulltext_index', $q)
                    YIELD node, score
                    RETURN node.chunk_id AS chunk_id, score
                    ORDER BY score DESC LIMIT $top_k
                """, q=search_query, top_k=top_k * 2)
                rows         = [dict(r) for r in ft_result]
                ft_ids       = [r["chunk_id"] for r in rows]
                ft_score_map = {r["chunk_id"]: r["score"] for r in rows}
        except Exception as e:
            logger.warning("Neo4j 全文索引检索也失败: %s", e)

    # 向量检索（Milvus 可用时才执行）
    vector_ids = []
    if strategy in ("parallel", "graph_augmented"):
        if not health_monitor.milvus.is_ok:
            logger.info("Milvus 不可用（已知 DOWN），跳过向量检索，仅使用全文结果")
        else:
            try:
                from ...services.embedder     import embed_query
                from ...services.milvus_store import search_sections
                vector_ids = [r["chunk_id"] for r in search_sections(embed_query(question), top_k=top_k * 2)]
            except Exception as e:
                logger.warning("向量检索失败: %s", e)

    # GNN 结构感知检索（strategy="gnn"）
    gnn_ids: list[str] = []
    if strategy == "gnn":
        try:
            from ...services.embedder   import embed_query
            from ...services.gnn_service import get_gnn_service
            gnn_svc = get_gnn_service()
            if gnn_svc.loaded:
                q_vec   = embed_query(question)
                gnn_ids = [r["chunk_id"] for r in gnn_svc.search(q_vec, top_k=top_k * 2)]
                logger.debug("GNN 检索返回 %d 个候选", len(gnn_ids))
            else:
                logger.warning("GNN 嵌入未加载，降级到全文检索")
        except Exception as e:
            logger.warning("GNN 检索失败，降级: %s", e)

    # 策略分发
    if strategy == "gnn":
        if gnn_ids and ft_ids:
            # GNN + 全文 RRF 融合，充分利用两路信号
            fused_ids = rrf_fusion(gnn_ids, ft_ids)[:top_k * 2]
        elif gnn_ids:
            fused_ids = gnn_ids[:top_k * 2]
        else:
            # GNN 不可用时退化为全文检索
            fused_ids = ft_ids[:top_k * 2]
    elif strategy == "parallel" and vector_ids:
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

    # ── 实体感知检索（Neo4j 可用时才执行） ──────────────────────────────────
    if not health_monitor.neo4j.is_ok:
        logger.info("Neo4j 不可用（已知 DOWN），跳过实体感知检索和图谱增强")
    else:
        try:
            with driver.session() as session:
                entity_result = session.run("""
                    MATCH (e)
                    WHERE (e:Tool OR e:Material OR e:Process)
                      AND toLower($question) CONTAINS toLower(e.name)
                    WITH e LIMIT 10
                    MATCH (s:Section)-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->(e)
                    RETURN DISTINCT s.chunk_id AS chunk_id
                    LIMIT 20
                """, question=question)
                entity_section_ids = [r["chunk_id"] for r in entity_result]
                if entity_section_ids:
                    seen_fused = set(fused_ids)
                    priority   = [cid for cid in entity_section_ids if cid not in seen_fused]
                    fused_ids  = priority + fused_ids
        except Exception as e:
            logger.warning("实体感知检索失败: %s", e)

    # ── 图谱增强扩展（含实体节点跨章节扩展） ─────────────────────────────────
    if strategy == "graph_augmented" and fused_ids:
        try:
            with driver.session() as session:
                result = session.run("""
                    UNWIND $chunk_ids AS cid
                    MATCH (s:Section {chunk_id: cid})
                    OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION]-(nb:Section)
                    OPTIONAL MATCH (p:Section)-[:HAS_SUBSECTION]->(s)
                    OPTIONAL MATCH (s)-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->(e)
                    OPTIONAL MATCH (sibling:Section)-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->(e)
                    WHERE sibling.chunk_id <> cid
                    WITH collect(DISTINCT s.chunk_id) +
                         collect(DISTINCT nb.chunk_id) +
                         collect(DISTINCT p.chunk_id) +
                         collect(DISTINCT sibling.chunk_id) AS all_ids
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

        # ── 跨文档推理：沿 REFERENCES 边追踪被引用规范 ────────────────────────
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
                seen    = set(fused_ids)
                for rid in ref_ids:
                    if rid not in seen:
                        fused_ids.append(rid)
                        seen.add(rid)
        except Exception as e:
            logger.warning("跨文档推理失败: %s", e)

    # ── 获取章节详情（Neo4j 不可用时从 ES 降级） ─────────────────────────────
    if health_monitor.neo4j.is_ok:
        sections = get_section_details(driver, fused_ids[:top_k * 2])
    else:
        # Neo4j 不可用：从 ES 获取章节内容作为降级方案
        try:
            from ...services.es_store import search_sections_es
            es_fallback = search_sections_es(question, top_k=top_k * 2)
            sections = [
                {k: r[k] for k in ("chunk_id", "doc_id", "number", "title", "content") if k in r}
                for r in es_fallback
            ]
        except Exception as e:
            logger.warning("ES 降级获取章节详情失败: %s", e)
            sections = []

    # Reranker 应用于 parallel / graph_augmented / sequential / gnn
    if sections and strategy in ("parallel", "graph_augmented", "sequential", "gnn"):
        try:
            from ...services.reranker import rerank
            sections = rerank(question, sections, top_k=top_k)
        except Exception as e:
            logger.warning("Reranker 失败: %s", e)

    return sections, ft_score_map
