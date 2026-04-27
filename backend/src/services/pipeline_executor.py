"""
pipeline_executor.py — 将 React Flow 节点图配置转换为实际检索链路执行。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .pipeline_node_handlers import NodeHandlersMixin

logger = logging.getLogger(__name__)

_SECTION_QUERY = """
    UNWIND $ids AS cid MATCH (s:Section {chunk_id: cid})
    RETURN s.chunk_id AS chunk_id, s.doc_id AS doc_id,
           s.number AS number, s.title AS title,
           s.content AS content, s.page_idx AS page_idx
"""


class PipelineExecutor(NodeHandlersMixin):
    """按拓扑顺序执行节点图，节点间通过端口名传递数据。"""

    def __init__(self, pipeline_config: dict, driver: Any):
        self.nodes: dict[str, dict] = {n["id"]: n for n in pipeline_config.get("nodes", [])}
        self.edges: list[dict] = pipeline_config.get("edges", [])
        self.driver = driver
        self._order: list[str] = self._topological_sort()

    def _topological_sort(self) -> list[str]:
        in_deg: dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in adj and tgt in in_deg:
                adj[src].append(tgt)
                in_deg[tgt] += 1
        queue = [nid for nid, d in in_deg.items() if d == 0]
        order: list[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for nb in adj[nid]:
                in_deg[nb] -= 1
                if in_deg[nb] == 0:
                    queue.append(nb)
        return order

    def _collect_inputs(self, node_id: str, node_outputs: dict[str, dict]) -> dict:
        query, candidates = "", []
        candidates_a: list = []
        candidates_b: list = []
        query_a, query_b = "", ""
        for edge in self.edges:
            if edge.get("target") != node_id:
                continue
            src_out = node_outputs.get(edge.get("source", ""), {})
            src_port = edge.get("sourceHandle") or ""
            tgt_port = edge.get("targetHandle") or ""
            port = src_port or tgt_port
            if port == "query_a":
                query_a = src_out.get("query", query_a)
            elif port == "query_b":
                query_b = src_out.get("query", query_b)
            elif port == "candidates_a":
                cands = src_out.get("candidates", [])
                if cands:
                    candidates_a = cands
            elif port == "candidates_b":
                cands = src_out.get("candidates", [])
                if cands:
                    candidates_b = cands
            elif port == "query" or (not port and "query" in src_out and "candidates" not in src_out):
                query = src_out.get("query", query)
            elif port == "candidates" or "candidates" in src_out:
                cands = src_out.get("candidates", [])
                if cands:
                    candidates.append(cands)
        return {
            "query": query, "candidates": candidates,
            "candidates_a": candidates_a, "candidates_b": candidates_b,
            "query_a": query_a, "query_b": query_b,
        }

    async def execute(self, question: str, user_id: str = "") -> dict:
        node_outputs: dict[str, dict] = {}
        for node_id in self._order:
            node = self.nodes[node_id]
            node_data = node.get("data", {})
            inputs = self._collect_inputs(node_id, node_outputs)
            if not inputs["query"]:
                inputs["query"] = question
            try:
                node_outputs[node_id] = await self._execute_node(
                    node_data.get("nodeType", ""), node_data.get("params", {}), inputs
                )
            except Exception as e:
                logger.warning("节点 %s 执行失败: %s", node_id, e)
                node_outputs[node_id] = {}
        answer, candidates = "", []
        for out in node_outputs.values():
            if "answer" in out:
                answer = out["answer"]
            if "candidates" in out:
                candidates = out["candidates"]
        return {"answer": answer, "candidates": candidates}

    async def _execute_node(self, node_type: str, params: dict, inputs: dict) -> dict:
        handlers = {
            # retrieval
            "vector_search":         self._run_vector_search,
            "bm25_search":           self._run_bm25_search,
            "graph_search":          self._run_graph_search,
            "keyword_search":        self._run_keyword_search,
            "fuzzy_search":          self._run_fuzzy_search,
            "semantic_search":       self._run_semantic_search,
            "multi_query_search":    self._run_multi_query_search,
            "section_filter_search": self._run_section_filter_search,
            "table_search":          self._run_table_search,
            # processing
            "rrf_fusion":            self._run_rrf_fusion,
            "rerank":                self._run_rerank,
            "hyde":                  self._run_hyde,
            "graph_expand":          self._run_graph_expand,
            "dedup":                 self._run_dedup,
            "score_filter":          self._run_score_filter,
            "context_window":        self._run_context_window,
            "keyword_highlight":     self._run_keyword_highlight,
            "doc_diversity":         self._run_doc_diversity,
            "query_expand":          self._run_query_expand,
            "query_rewrite":         self._run_query_rewrite,
            "mmr_diversity":         self._run_mmr_diversity,
            "cross_encoder":         self._run_cross_encoder,
            "entity_link":           self._run_entity_link,
            # generation
            "llm_generate":          self._run_llm_generate,
            "self_rag":              self._run_self_rag,
            "summary_generate":      self._run_summary_generate,
            "structured_extract":    self._run_structured_extract,
            "checklist_generate":    self._run_checklist_generate,
            "compare_generate":      self._run_compare_generate,
            "citation_generate":     self._run_citation_generate,
            # control
            "condition_branch":      self._run_condition_branch,
            "merge":                 self._run_merge,
            "cache_check":           self._run_cache_check,
            "ab_test":               self._run_ab_test,
            "feedback_loop":         self._run_feedback_loop,
        }
        handler = handlers.get(node_type)
        if not handler:
            raise ValueError(f"未知节点类型: {node_type}")
        return await handler(params, inputs)

    def _tag(self, sections: list[dict], source_type: str, trace: str, **flags: bool) -> list[dict]:
        for s in sections:
            s.setdefault("source_type", [source_type])
            s.setdefault("retrieval_trace", [trace])
            for k, v in flags.items():
                s[k] = v
        return sections

    async def _run_vector_search(self, params: dict, inputs: dict) -> dict:
        top_k, question = int(params.get("top_k", 10)), inputs["query"]
        def _fn():
            from .retrieval.embedder import embed_query
            from .storage.milvus_store import search_sections
            return search_sections(embed_query(question), top_k=top_k)
        try:
            return {"candidates": self._tag(await asyncio.to_thread(_fn), "vector", "vector:milvus", is_vector_hit=True)}
        except Exception as e:
            logger.warning("vector_search 失败: %s", e)
            return {"candidates": []}

    async def _run_bm25_search(self, params: dict, inputs: dict) -> dict:
        top_k, question = int(params.get("top_k", 10)), inputs["query"]
        def _fn():
            from .storage.es_store import search_sections_es
            return search_sections_es(question, top_k=top_k)
        try:
            return {"candidates": self._tag(await asyncio.to_thread(_fn), "fulltext", "fulltext:es", is_fulltext_hit=True)}
        except Exception as e:
            logger.warning("bm25_search 失败: %s", e)
            return {"candidates": []}

    async def _run_graph_search(self, params: dict, inputs: dict) -> dict:
        top_k, depth, question = int(params.get("top_k", 10)), int(params.get("depth", 2)), inputs["query"]
        def _fn():
            with self.driver.session() as s:
                ids = [r["chunk_id"] for r in s.run(
                    "CALL db.index.fulltext.queryNodes('cps_fulltext_index', $q) "
                    "YIELD node, score RETURN node.chunk_id AS chunk_id ORDER BY score DESC LIMIT $n",
                    q=question, n=top_k,
                )]
                if not ids:
                    return []
                sections = [dict(r) for r in s.run(_SECTION_QUERY, ids=ids)]
            return self._tag(sections, "graph", f"graph:fulltext_depth{depth}", is_graph_expanded=True)
        try:
            return {"candidates": await asyncio.to_thread(_fn)}
        except Exception as e:
            logger.warning("graph_search 失败: %s", e)
            return {"candidates": []}

    async def _run_rrf_fusion(self, params: dict, inputs: dict) -> dict:
        k, all_lists = int(params.get("k", 60)), inputs["candidates"]
        if not all_lists:
            return {"candidates": []}
        scores: dict[str, float] = {}
        id_to_sec: dict[str, dict] = {}
        for lst in all_lists:
            for rank, sec in enumerate(lst, start=1):
                cid = sec.get("chunk_id", "")
                if cid:
                    scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
                    id_to_sec[cid] = sec
        return {"candidates": [id_to_sec[c] for c in sorted(scores, key=scores.__getitem__, reverse=True) if c in id_to_sec]}

    async def _run_rerank(self, params: dict, inputs: dict) -> dict:
        top_k = int(params.get("top_k", 5))
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat:
            return {"candidates": []}
        def _fn():
            from .retrieval.reranker import rerank
            return rerank(inputs["query"], flat, top_k=top_k)
        try:
            return {"candidates": await asyncio.to_thread(_fn)}
        except Exception as e:
            logger.warning("rerank 失败，返回原始列表: %s", e)
            return {"candidates": flat[:top_k]}

    async def _run_hyde(self, params: dict, inputs: dict) -> dict:
        alpha, question = float(params.get("alpha", 0.5)), inputs["query"]
        def _fn():
            from .retrieval.hyde_service import get_hyde_service
            return get_hyde_service().generate_hypothetical_answer(question)
        try:
            hyp = await asyncio.to_thread(_fn)
            return {"query": f"{question}\n\n假设答案：{hyp}" if alpha > 0 else question}
        except Exception as e:
            logger.warning("hyde 失败: %s", e)
            return {"query": question}

    async def _run_graph_expand(self, params: dict, inputs: dict) -> dict:
        hops = int(params.get("hops", 1))
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat:
            return {"candidates": []}
        seed_ids = [s["chunk_id"] for s in flat if s.get("chunk_id")][:5]
        def _fn():
            with self.driver.session() as s:
                rec = s.run(
                    "UNWIND $ids AS cid MATCH (s:Section {chunk_id: cid}) "
                    "OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION*1..%d]-(nb:Section) "
                    "RETURN collect(DISTINCT nb.chunk_id) AS nb_ids" % hops,
                    ids=seed_ids,
                ).single()
                nb_ids = [x for x in (rec["nb_ids"] if rec else []) if x]
                if not nb_ids:
                    return []
                secs = [dict(r) for r in s.run(_SECTION_QUERY, ids=nb_ids)]
            return self._tag(secs, "graph", "graph:neighbor_expand", is_graph_expanded=True)
        try:
            extra = await asyncio.to_thread(_fn)
            seen = {s["chunk_id"] for s in flat}
            return {"candidates": flat + [s for s in extra if s.get("chunk_id") not in seen]}
        except Exception as e:
            logger.warning("graph_expand 失败: %s", e)
            return {"candidates": flat}

    async def _run_llm_generate(self, params: dict, inputs: dict) -> dict:
        question = inputs["query"]
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat:
            return {"answer": "在知识库中未找到相关章节，请确认文件已入库。", "candidates": []}
        context = "\n\n".join(
            f"[{s.get('doc_id', '')} §{s.get('number', '')}] {s.get('title', '')}\n{s.get('content', '')}"
            for s in flat
        )
        def _fn():
            from .ai.llm import generate_answer_with_usage
            answer, _ = generate_answer_with_usage(question=question, context=context, history=[])
            return answer
        try:
            answer = await asyncio.to_thread(_fn)
        except Exception as e:
            logger.warning("llm_generate 失败: %s", e)
            answer = f"检索到 {len(flat)} 个相关章节，但 LLM 生成失败。"
        return {"answer": answer, "candidates": flat}
