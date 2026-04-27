"""
pipeline_node_handlers.py — 检索 + 处理节点 handler Mixin。
由 PipelineExecutor 继承；生成/控制节点由 NodeHandlersGenMixin 提供。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .pipeline_node_gen_handlers import NodeHandlersGenMixin

logger = logging.getLogger(__name__)

_SECTION_QUERY = """
    UNWIND $ids AS cid MATCH (s:Section {chunk_id: cid})
    RETURN s.chunk_id AS chunk_id, s.doc_id AS doc_id,
           s.number AS number, s.title AS title,
           s.content AS content, s.page_idx AS page_idx
"""


class NodeHandlersMixin(NodeHandlersGenMixin):
    driver: Any  # provided by PipelineExecutor

    def _tag(self, sections: list[dict], source_type: str, trace: str, **flags: bool) -> list[dict]:
        raise NotImplementedError  # implemented in PipelineExecutor

    # ── 检索节点 ──────────────────────────────────────────────────────────

    async def _run_keyword_search(self, params: dict, inputs: dict) -> dict:
        top_k, question = int(params.get("top_k", 10)), inputs["query"]
        operator = params.get("operator", "OR")
        fields = params.get("fields", ["title", "content"])
        def _fn():
            from .storage.es_store import search_sections_es
            return search_sections_es(question, top_k=top_k, operator=operator, fields=fields)
        try:
            return {"candidates": self._tag(await asyncio.to_thread(_fn), "fulltext", f"keyword:{operator}", is_fulltext_hit=True)}
        except Exception as e:
            logger.warning("keyword_search 失败: %s", e)
            return {"candidates": []}

    async def _run_fuzzy_search(self, params: dict, inputs: dict) -> dict:
        top_k, question = int(params.get("top_k", 10)), inputs["query"]
        fuzziness = params.get("fuzziness", "AUTO")
        def _fn():
            from .storage.es_store import search_sections_es
            return search_sections_es(question, top_k=top_k, fuzziness=fuzziness)
        try:
            return {"candidates": self._tag(await asyncio.to_thread(_fn), "fulltext", f"fuzzy:{fuzziness}", is_fulltext_hit=True)}
        except Exception as e:
            logger.warning("fuzzy_search 失败: %s", e)
            return {"candidates": []}

    async def _run_semantic_search(self, params: dict, inputs: dict) -> dict:
        top_k, question = int(params.get("top_k", 10)), inputs["query"]
        threshold = float(params.get("threshold", 0.7))
        def _fn():
            from .retrieval.embedder import embed_query
            from .storage.milvus_store import search_sections
            results = search_sections(embed_query(question), top_k=top_k)
            return [r for r in results if r.get("score", 1.0) >= threshold]
        try:
            return {"candidates": self._tag(await asyncio.to_thread(_fn), "vector", "semantic:milvus", is_vector_hit=True)}
        except Exception as e:
            logger.warning("semantic_search 失败: %s", e)
            return {"candidates": []}

    async def _run_multi_query_search(self, params: dict, inputs: dict) -> dict:
        question = inputs["query"]
        num_q, top_k = int(params.get("num_queries", 3)), int(params.get("top_k", 10))
        def _gen():
            from .ai.llm import generate_answer_with_usage
            prompt = f"将以下问题改写为{num_q}个不同表达（每行一个）：\n{question}"
            text, _ = generate_answer_with_usage(question=prompt, context="", history=[])
            return [question] + [l.strip() for l in text.splitlines() if l.strip()][:num_q - 1]
        def _search(q: str):
            from .retrieval.embedder import embed_query
            from .storage.milvus_store import search_sections
            return search_sections(embed_query(q), top_k=top_k)
        try:
            queries = await asyncio.to_thread(_gen)
            seen, results = set(), []
            for q in queries:
                for s in await asyncio.to_thread(_search, q):
                    cid = s.get("chunk_id", "")
                    if cid and cid not in seen:
                        seen.add(cid); results.append(s)
            return {"candidates": self._tag(results, "vector", "multi_query", is_vector_hit=True)}
        except Exception as e:
            logger.warning("multi_query_search 失败: %s", e)
            return {"candidates": []}

    async def _run_section_filter_search(self, params: dict, inputs: dict) -> dict:
        question, top_k = inputs["query"], int(params.get("top_k", 10))
        level_min, level_max = int(params.get("level_min", 1)), int(params.get("level_max", 4))
        doc_filter = [d.strip() for d in str(params.get("doc_filter", "")).split(",") if d.strip()]
        def _fn():
            from .retrieval.embedder import embed_query
            from .storage.milvus_store import search_sections
            results = search_sections(embed_query(question), top_k=top_k * 3)
            filtered = []
            for r in results:
                num = str(r.get("number", ""))
                depth = len(num.split("."))
                if not (level_min <= depth <= level_max):
                    continue
                if doc_filter and r.get("doc_id") not in doc_filter:
                    continue
                filtered.append(r)
            return filtered[:top_k]
        try:
            return {"candidates": self._tag(await asyncio.to_thread(_fn), "vector", "section_filter", is_vector_hit=True)}
        except Exception as e:
            logger.warning("section_filter_search 失败: %s", e)
            return {"candidates": []}

    async def _run_table_search(self, params: dict, inputs: dict) -> dict:
        question, top_k = inputs["query"], int(params.get("top_k", 5))
        min_rows = int(params.get("min_rows", 2))
        def _fn():
            with self.driver.session() as s:
                ids = [r["chunk_id"] for r in s.run(
                    "CALL db.index.fulltext.queryNodes('cps_fulltext_index', $q) "
                    "YIELD node, score WHERE node.has_table = true AND coalesce(node.table_rows, 0) >= $mr "
                    "RETURN node.chunk_id AS chunk_id ORDER BY score DESC LIMIT $n",
                    q=question, mr=min_rows, n=top_k,
                )]
                if not ids: return []
                return [dict(r) for r in s.run(_SECTION_QUERY, ids=ids)]
        try:
            return {"candidates": self._tag(await asyncio.to_thread(_fn), "fulltext", "table_search", is_fulltext_hit=True)}
        except Exception as e:
            logger.warning("table_search 失败: %s", e)
            return {"candidates": []}

    # ── 处理节点 ──────────────────────────────────────────────────────────

    async def _run_dedup(self, params: dict, inputs: dict) -> dict:
        threshold = float(params.get("similarity_threshold", 0.9))
        keep = params.get("keep", "first")
        flat = [s for lst in inputs["candidates"] for s in lst]
        seen_texts: list[str] = []
        result: list[dict] = []
        for s in flat:
            text = (s.get("content") or "")[:200]
            if any(_jaccard(text, t) >= threshold for t in seen_texts):
                if keep == "highest_score":
                    result = [s if s.get("score", 0) > r.get("score", 0) else r
                               for r in result if r.get("chunk_id") == s.get("chunk_id")] or result
                continue
            seen_texts.append(text)
            result.append(s)
        return {"candidates": result}

    async def _run_score_filter(self, params: dict, inputs: dict) -> dict:
        min_score = float(params.get("min_score", 0.5))
        max_results = int(params.get("max_results", 10))
        flat = [s for lst in inputs["candidates"] for s in lst]
        filtered = [s for s in flat if s.get("score", 1.0) >= min_score]
        return {"candidates": filtered[:max_results]}

    async def _run_context_window(self, params: dict, inputs: dict) -> dict:
        before, after = int(params.get("before_sections", 1)), int(params.get("after_sections", 1))
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat: return {"candidates": []}
        seed_ids = [s["chunk_id"] for s in flat if s.get("chunk_id")]
        def _fn():
            with self.driver.session() as s:
                rec = s.run(
                    "UNWIND $ids AS cid MATCH (s:Section {chunk_id: cid}) "
                    f"OPTIONAL MATCH (s)<-[:NEXT_SECTION*1..{before}]-(prev:Section) "
                    f"OPTIONAL MATCH (s)-[:NEXT_SECTION*1..{after}]->(nxt:Section) "
                    "RETURN collect(DISTINCT prev.chunk_id) + collect(DISTINCT nxt.chunk_id) AS nb_ids",
                    ids=seed_ids,
                ).single()
                nb_ids = [x for x in (rec["nb_ids"] if rec else []) if x]
                if not nb_ids: return []
                return [dict(r) for r in s.run(_SECTION_QUERY, ids=nb_ids)]
        try:
            extra = await asyncio.to_thread(_fn)
            seen = {s["chunk_id"] for s in flat}
            return {"candidates": flat + self._tag([s for s in extra if s.get("chunk_id") not in seen], "graph", "context_window")}
        except Exception as e:
            logger.warning("context_window 失败: %s", e)
            return {"candidates": flat}

    async def _run_keyword_highlight(self, params: dict, inputs: dict) -> dict:
        query, flat = inputs["query"], [s for lst in inputs["candidates"] for s in lst]
        max_frag = int(params.get("max_fragments", 3))
        frag_size = int(params.get("fragment_size", 150))
        keywords = [w for w in query.split() if len(w) > 1]
        for s in flat:
            content = s.get("content", "")
            frags = []
            for kw in keywords:
                idx = content.lower().find(kw.lower())
                if idx >= 0:
                    start = max(0, idx - frag_size // 2)
                    frags.append(content[start: start + frag_size])
                if len(frags) >= max_frag:
                    break
            s["highlight"] = frags or [content[:frag_size]]
        return {"candidates": flat}

    async def _run_doc_diversity(self, params: dict, inputs: dict) -> dict:
        max_per_doc = int(params.get("max_per_doc", 2))
        total_keep = int(params.get("total_keep", 8))
        flat = [s for lst in inputs["candidates"] for s in lst]
        doc_counts: dict[str, int] = {}
        result = []
        for s in flat:
            doc = s.get("doc_id", "")
            if doc_counts.get(doc, 0) < max_per_doc:
                doc_counts[doc] = doc_counts.get(doc, 0) + 1
                result.append(s)
            if len(result) >= total_keep:
                break
        return {"candidates": result}

    async def _run_cross_encoder(self, params: dict, inputs: dict) -> dict:
        top_k = int(params.get("top_k", 5))
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat: return {"candidates": []}
        def _fn():
            from .retrieval.reranker import rerank
            return rerank(inputs["query"], flat, top_k=top_k)
        try:
            return {"candidates": await asyncio.to_thread(_fn)}
        except Exception as e:
            logger.warning("cross_encoder 失败: %s", e)
            return {"candidates": flat[:top_k]}

    async def _run_entity_link(self, params: dict, inputs: dict) -> dict:
        flat = [s for lst in inputs["candidates"] for s in lst]
        max_docs = int(params.get("max_entity_docs", 3))
        expand = bool(params.get("expand_entity", True))
        if not flat or not expand: return {"candidates": flat}
        def _fn():
            with self.driver.session() as s:
                seed_ids = [x["chunk_id"] for x in flat if x.get("chunk_id")][:5]
                rec = s.run(
                    "UNWIND $ids AS cid MATCH (sec:Section {chunk_id: cid})-[:MENTIONS]->(e:Entity) "
                    "MATCH (other:Section)-[:MENTIONS]->(e) WHERE other.chunk_id <> cid "
                    "RETURN collect(DISTINCT other.chunk_id)[..$n] AS nb_ids",
                    ids=seed_ids, n=max_docs * 3,
                ).single()
                nb_ids = [x for x in (rec["nb_ids"] if rec else []) if x]
                if not nb_ids: return []
                return [dict(r) for r in s.run(_SECTION_QUERY, ids=nb_ids)]
        try:
            extra = await asyncio.to_thread(_fn)
            seen = {s["chunk_id"] for s in flat}
            return {"candidates": flat + self._tag([s for s in extra if s.get("chunk_id") not in seen], "graph", "entity_link", is_graph_expanded=True)}
        except Exception as e:
            logger.warning("entity_link 失败: %s", e)
            return {"candidates": flat}


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / len(sa | sb) if sa | sb else 0.0
