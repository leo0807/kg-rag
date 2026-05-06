from __future__ import annotations

"""
检索核心：RRF融合、章节获取、多策略检索
"""
import json
import logging
import re
from neo4j import Driver

_ROW_RE = re.compile(r'^(.+)_row_(\d+)$')
from ...services.infra.health import health_monitor
from .source_meta import _ensure_source_meta, _mark_sources, _finalize_source_meta
from .graph_expansion import apply_entity_aware, apply_graph_augmented

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

    section_ids: list[str] = []
    row_id_info: dict[str, tuple[str, int]] = {}
    for cid in chunk_ids:
        m = _ROW_RE.match(cid)
        if m:
            row_id_info[cid] = (m.group(1), int(m.group(2)))
        else:
            section_ids.append(cid)

    results: dict[str, dict] = {}

    if section_ids:
        with driver.session() as session:
            r = session.run("""
                UNWIND $chunk_ids AS cid
                MATCH (s:Section {chunk_id: cid})
                RETURN s.chunk_id AS chunk_id, s.doc_id AS doc_id,
                       s.number AS number, s.title AS title,
                       s.content AS content, s.page_idx AS page_idx, s.bbox AS bbox
            """, chunk_ids=section_ids)
            for row in r:
                results[row["chunk_id"]] = dict(row)

    if row_id_info:
        table_ids = list({info[0] for info in row_id_info.values()})
        with driver.session() as session:
            r = session.run("""
                UNWIND $table_ids AS tid
                MATCH (t:Table {table_id: tid})
                OPTIONAL MATCH (sec:Section)-[:HAS_TABLE]->(t)
                RETURN t.table_id AS table_id, t.doc_id AS doc_id,
                       t.headers AS headers, t.structured_data AS structured_data,
                       t.page_index AS page_index,
                       sec.number AS number, sec.title AS title
            """, table_ids=table_ids)
            table_info = {row["table_id"]: dict(row) for row in r}

        for cid, (table_id, row_idx) in row_id_info.items():
            tinfo = table_info.get(table_id)
            if not tinfo:
                continue
            headers: list[str] = tinfo.get("headers") or []
            struct: list[dict] = []
            try:
                struct = json.loads(tinfo.get("structured_data") or "[]")
            except Exception:
                pass
            row_data = struct[row_idx - 1] if 0 < row_idx <= len(struct) else {}
            results[cid] = {
                "chunk_id":     cid,
                "doc_id":       tinfo.get("doc_id") or "",
                "number":       tinfo.get("number") or "",
                "title":        tinfo.get("title") or "",
                "content":      " | ".join(f"{k}: {v}" for k, v in row_data.items()),
                "page_idx":     tinfo.get("page_index"),
                "bbox":         None,
                "content_type": "table_row",
                "table_id":     table_id,
                "row_index":    row_idx,
                "headers":      headers,
                "row_data":     row_data,
            }

    return [results[cid] for cid in chunk_ids if cid in results]


def do_retrieval(
    driver:     Driver,
    question:   str,
    strategy:   str,
    top_k:      int,
    use_hyde:   bool  = False,
    hyde_alpha: float = 0.5,
    doc_id:     str   = "",
):
    """返回 (sections, ft_score_map)"""
    source_meta: dict[str, dict] = {}

    from ...services.retrieval.query_expander import expand_query
    search_query, expansion_info = expand_query(driver, question)

    # ES 全文检索
    ft_ids, ft_score_map = [], {}
    if health_monitor.elasticsearch.is_ok:
        try:
            from ...services.storage.es_store import search_sections_es
            es_results   = search_sections_es(search_query, top_k=top_k * 2, doc_id=doc_id)
            ft_ids       = [r["chunk_id"] for r in es_results]
            ft_score_map = {r["chunk_id"]: r["score"] for r in es_results}
            _mark_sources(source_meta, ft_ids, source_type="fulltext", trace="fulltext:es", is_fulltext_hit=True)
        except Exception as e:
            logger.warning("ES 检索失败，降级到 Neo4j 全文索引: %s", e)
            health_monitor.elasticsearch.state = health_monitor.elasticsearch.state.__class__.DOWN
    else:
        logger.info("ES 不可用（已知 DOWN），跳过 ES 检索")

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
                rows         = [dict(r) for r in ft_result]
                ft_ids       = [r["chunk_id"] for r in rows]
                ft_score_map = {r["chunk_id"]: r["score"] for r in rows}
                _mark_sources(source_meta, ft_ids, source_type="fulltext", trace="fulltext:neo4j", is_fulltext_hit=True)
        except Exception as e:
            logger.warning("Neo4j 全文索引检索也失败: %s", e)

    # 向量检索
    vector_ids = []
    if strategy in ("parallel", "graph_augmented"):
        if not health_monitor.milvus.is_ok:
            logger.info("Milvus 不可用（已知 DOWN），跳过向量检索")
        else:
            try:
                from ...services.retrieval.embedder import embed_query
                from ...services.storage.milvus_store import search_sections
                if use_hyde:
                    from ...services.retrieval.hyde_service import get_hyde_service
                    query_vec = get_hyde_service().hybrid_embedding(question, alpha=hyde_alpha)
                    logger.info("HyDE 增强向量检索（alpha=%.2f）", hyde_alpha)
                else:
                    query_vec = embed_query(question)
                vector_ids = [r["chunk_id"] for r in search_sections(query_vec, top_k=top_k * 2, doc_id=doc_id)]
                _mark_sources(source_meta, vector_ids, source_type="vector", trace="vector:milvus", is_vector_hit=True)
            except Exception as e:
                logger.warning("向量检索失败: %s", e)

    # ES 混合检索
    if strategy == "hybrid_es":
        try:
            from ...services.retrieval.embedder import embed_query
            from ...services.storage.es_store import hybrid_search
            import redis as _redis
            from ...core.config import settings as _cfg
            _alpha = 0.5
            try:
                _r = _redis.from_url(_cfg.REDIS_URL)
                _v = _r.get("search:hybrid_alpha")
                if _v:
                    _alpha = float(_v)
            except Exception:
                pass
            query_vec = embed_query(question)
            es_hits = hybrid_search(query=question, query_embedding=query_vec,
                                    top_k=top_k * 2, doc_ids=[doc_id] if doc_id else None)
            sections = []
            for h in es_hits:
                cid = h.get("chunk_id", "")
                meta = _ensure_source_meta(source_meta, cid)
                meta["source_type"].add("es_hybrid")
                meta["retrieval_trace"].append("es_hybrid:rrf")
                meta["is_fulltext_hit"] = True
                meta["is_vector_hit"] = True
                sections.append({
                    "chunk_id": cid, "doc_id": h.get("doc_id", ""),
                    "number": h.get("number", ""), "title": h.get("title", ""),
                    "content": h.get("content", ""), "score": h.get("es_score", 0.0),
                    **_finalize_source_meta(source_meta, cid),
                })
            sections = sections[:top_k]
            logger.info("hybrid_es 返回 %d 条（alpha=%.2f）", len(sections), _alpha)
            return sections, {}
        except Exception as exc:
            logger.warning("hybrid_es 检索失败，降级到 parallel: %s", exc)

    # GNN 检索
    gnn_ids: list[str] = []
    if strategy == "gnn":
        try:
            from ...services.retrieval.embedder import embed_query
            from ...services.storage.gnn_service import get_gnn_service
            gnn_svc = get_gnn_service()
            if gnn_svc.loaded:
                q_vec   = embed_query(question)
                gnn_ids = [r["chunk_id"] for r in gnn_svc.search(q_vec, top_k=top_k * 2, doc_id=doc_id)]
                _mark_sources(source_meta, gnn_ids, source_type="gnn", trace="gnn:graphsage", is_gnn_hit=True)
            else:
                logger.warning("GNN 嵌入未加载，降级到全文检索")
        except Exception as e:
            logger.warning("GNN 检索失败，降级: %s", e)

    # 策略分发
    if strategy == "gnn":
        fused_ids = rrf_fusion(gnn_ids, ft_ids)[:top_k * 2] if gnn_ids and ft_ids else (gnn_ids or ft_ids)[:top_k * 2]
    elif strategy == "parallel" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]
    elif strategy == "sequential":
        fused_ids = list(ft_ids[:top_k])
        if len(fused_ids) < top_k:
            try:
                from ...services.retrieval.embedder import embed_query
                from ...services.storage.milvus_store import search_sections
                _seq_vec = get_hyde_service().hybrid_embedding(question, alpha=hyde_alpha) if use_hyde else embed_query(question)  # type: ignore[name-defined]
                seen = set(fused_ids)
                for r in search_sections(_seq_vec, top_k=top_k, doc_id=doc_id):
                    if r["chunk_id"] not in seen and len(fused_ids) < top_k:
                        fused_ids.append(r["chunk_id"]); seen.add(r["chunk_id"])
            except Exception as e:
                logger.warning("串行向量补充失败: %s", e)
    elif strategy == "graph_augmented" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]
    else:
        fused_ids = ft_ids[:top_k * 2]

    # 实体感知检索
    if health_monitor.neo4j.is_ok:
        fused_ids = apply_entity_aware(driver, fused_ids, source_meta, question, doc_id)
    else:
        logger.info("Neo4j 不可用（已知 DOWN），跳过实体感知检索和图谱增强")

    # 图谱增强
    if strategy == "graph_augmented" and fused_ids:
        fused_ids = apply_graph_augmented(driver, fused_ids, source_meta, doc_id)

    # 获取章节详情
    if health_monitor.neo4j.is_ok:
        sections = get_section_details(driver, fused_ids[:top_k * 2])
    else:
        try:
            from ...services.storage.es_store import search_sections_es
            es_fallback = search_sections_es(question, top_k=top_k * 2, doc_id=doc_id)
            sections = [{k: r[k] for k in ("chunk_id", "doc_id", "number", "title", "content") if k in r} for r in es_fallback]
            _mark_sources(source_meta, [s["chunk_id"] for s in sections if s.get("chunk_id")],
                         source_type="fulltext", trace="fulltext:es_fallback", is_fulltext_hit=True)
        except Exception as e:
            logger.warning("ES 降级获取章节详情失败: %s", e)
            sections = []

    # Reranker
    from ...core.config import settings as _s
    if _s.RERANKER_ENABLED and sections and strategy in ("parallel", "graph_augmented", "sequential", "gnn", "hybrid_es"):
        try:
            from ...services.retrieval.reranker import rerank
            sections = rerank(question, sections, top_k=top_k)
        except Exception as e:
            logger.warning("Reranker 失败: %s", e)

    for section in sections:
        section.update(_finalize_source_meta(source_meta, section.get("chunk_id", "")))

    # entity blacklist downweighting
    try:
        import redis as _r_mod, json as _json
        from ...core.config import settings as _cfg
        _r = _r_mod.from_url(_cfg.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        _bl = set(_json.loads(_r.get("entity:blacklist") or "[]"))
        if _bl:
            for s in sections:
                hits = sum(1 for t in _bl if t in (s.get("content") or ""))
                if hits:
                    s["score"] = round((s.get("score") or 1.0) * 0.3, 4)
            sections.sort(key=lambda x: x.get("score") or 0, reverse=True)
    except Exception:
        pass

    return sections, ft_score_map, expansion_info
