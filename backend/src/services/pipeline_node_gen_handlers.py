"""
pipeline_node_gen_handlers.py — 生成节点 + 控制节点 handler Mixin。
由 NodeHandlersMixin 继承。
"""
from __future__ import annotations

import asyncio
import logging
import random

logger = logging.getLogger(__name__)


class NodeHandlersGenMixin:

    # ── 查询变换节点 ─────────────────────────────────────────────────────

    async def _run_query_expand(self, params: dict, inputs: dict) -> dict:
        question = inputs["query"]
        expand_type = params.get("expand_type", "synonym")
        max_terms = int(params.get("max_terms", 5))
        if expand_type in ("llm", "both"):
            def _fn():
                from .ai.llm import generate_answer_with_usage
                prompt = f"列出与「{question}」相关的{max_terms}个近义词/相关词（逗号分隔）："
                text, _ = generate_answer_with_usage(question=prompt, context="", history=[])
                return text.strip()
            try:
                terms = await asyncio.to_thread(_fn)
                return {"query": f"{question} {terms}"}
            except Exception as e:
                logger.warning("query_expand llm 失败: %s", e)
        return {"query": question}

    async def _run_query_rewrite(self, params: dict, inputs: dict) -> dict:
        question = inputs["query"]
        style = params.get("style", "technical")
        add_context = bool(params.get("add_context", True))
        ctx = "（航空制造工艺领域）" if add_context else ""
        style_map = {"technical": "技术规范", "simplified": "简洁", "formal": "正式"}
        def _fn():
            from .ai.llm import generate_answer_with_usage
            prompt = f"用{style_map.get(style, '技术')}语言{ctx}改写以下问题，只输出改写后的问题：\n{question}"
            text, _ = generate_answer_with_usage(question=prompt, context="", history=[])
            return text.strip() or question
        try:
            return {"query": await asyncio.to_thread(_fn)}
        except Exception as e:
            logger.warning("query_rewrite 失败: %s", e)
            return {"query": question}

    async def _run_mmr_diversity(self, params: dict, inputs: dict) -> dict:
        lam = float(params.get("lambda_param", 0.5))
        top_k = int(params.get("top_k", 5))
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat: return {"candidates": []}
        def _fn():
            from .retrieval.embedder import embed_query
            q_emb = embed_query(inputs["query"])
            return _mmr(flat, q_emb, lam, top_k)
        try:
            return {"candidates": await asyncio.to_thread(_fn)}
        except Exception as e:
            logger.warning("mmr_diversity 失败，返回原列表: %s", e)
            return {"candidates": flat[:top_k]}

    # ── 生成节点 ──────────────────────────────────────────────────────────

    async def _llm_with_prompt(self, system_hint: str, inputs: dict, max_tokens: int) -> dict:
        question = inputs["query"]
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat:
            return {"answer": "未找到相关章节。", "candidates": []}
        context = "\n\n".join(
            f"[{s.get('doc_id', '')} §{s.get('number', '')}] {s.get('title', '')}\n{s.get('content', '')}"
            for s in flat
        )
        def _fn():
            from .ai.llm import generate_answer_with_usage
            full_q = f"{system_hint}\n\n问题：{question}"
            answer, _ = generate_answer_with_usage(question=full_q, context=context, history=[], max_tokens=max_tokens)
            return answer
        try:
            answer = await asyncio.to_thread(_fn)
        except Exception as e:
            logger.warning("llm 调用失败: %s", e)
            answer = f"检索到 {len(flat)} 个相关章节，但 LLM 生成失败。"
        return {"answer": answer, "candidates": flat}

    async def _run_self_rag(self, params: dict, inputs: dict) -> dict:
        question = inputs["query"]
        flat = [s for lst in inputs["candidates"] for s in lst]
        if not flat:
            return {"answer": "未找到相关章节。", "candidates": []}
        context = "\n\n".join(
            f"[{s.get('doc_id', '')} §{s.get('number', '')}] {s.get('content', '')}"
            for s in flat
        )
        def _fn():
            from .ai.llm import generate_answer_with_usage
            prompt = (
                f"请先判断以下检索内容是否与问题相关（回答「相关」或「不相关」），"
                f"若相关则给出答案，否则说明无法回答。\n\n问题：{question}"
            )
            answer, _ = generate_answer_with_usage(question=prompt, context=context, history=[])
            return answer
        try:
            answer = await asyncio.to_thread(_fn)
        except Exception as e:
            logger.warning("self_rag 失败: %s", e)
            answer = f"检索到 {len(flat)} 个章节，但生成失败。"
        return {"answer": answer, "candidates": flat}

    async def _run_summary_generate(self, params: dict, inputs: dict) -> dict:
        fmt = params.get("format", "paragraph")
        hint = {"paragraph": "请生成一段连贯的总结。", "bullets": "请用要点列表格式总结。", "numbered": "请用编号列表格式总结。"}.get(fmt, "请总结以下内容。")
        return await self._llm_with_prompt(hint, inputs, int(params.get("max_tokens", 300)))

    async def _run_structured_extract(self, params: dict, inputs: dict) -> dict:
        schema = params.get("output_schema", '{"value": "", "unit": ""}')
        etype = params.get("extract_type", "parameter")
        hint = f"请从文档中提取{etype}信息，严格按照以下 JSON 结构输出：\n{schema}"
        return await self._llm_with_prompt(hint, inputs, 500)

    async def _run_checklist_generate(self, params: dict, inputs: dict) -> dict:
        max_items = int(params.get("max_items", 10))
        include_src = bool(params.get("include_source", True))
        src_note = "每条末尾注明来源章节编号。" if include_src else ""
        hint = f"请生成不超过 {max_items} 条操作清单。{src_note}"
        return await self._llm_with_prompt(hint, inputs, 600)

    async def _run_compare_generate(self, params: dict, inputs: dict) -> dict:
        aspects = params.get("aspects", "材料, 工艺, 参数, 注意事项")
        fmt = params.get("format", "table")
        hint = f"请对比分析以下维度：{aspects}。{'用 Markdown 表格输出。' if fmt == 'table' else '用段落形式输出。'}"
        return await self._llm_with_prompt(hint, inputs, 800)

    async def _run_citation_generate(self, params: dict, inputs: dict) -> dict:
        style = params.get("citation_style", "inline")
        hint = {"inline": "回答时在相关陈述后以 [文档编号§章节号] 形式内联引用。",
                "footnote": "回答后附脚注列出引用来源。",
                "endnote": "回答后附参考文献列表。"}.get(style, "回答时标明引用来源。")
        return await self._llm_with_prompt(hint, inputs, int(params.get("max_tokens", 800)))

    # ── 控制节点 ──────────────────────────────────────────────────────────

    async def _run_condition_branch(self, params: dict, inputs: dict) -> dict:
        condition = params.get("condition", "query_length")
        threshold = int(params.get("threshold", 20))
        query = inputs["query"]
        if condition == "always_a":
            go_a = True
        elif condition == "keyword_match":
            go_a = any(w in query for w in ["是什么", "定义", "介绍"])
        else:
            go_a = len(query) <= threshold
        return {"query_a": query if go_a else "", "query_b": "" if go_a else query}

    async def _run_merge(self, params: dict, inputs: dict) -> dict:
        strategy = params.get("strategy", "concat")
        dedup = bool(params.get("dedup_after", True))
        a = inputs.get("candidates_a") or []
        b = inputs.get("candidates_b") or []
        flat_a = a if (a and not isinstance(a[0], list)) else [s for lst in a for s in lst]
        flat_b = b if (b and not isinstance(b[0], list)) else [s for lst in b for s in lst]
        if strategy == "interleave":
            merged = [s for pair in zip(flat_a, flat_b) for s in pair]
            merged += flat_a[len(flat_b):] + flat_b[len(flat_a):]
        elif strategy == "union":
            merged = flat_a + [s for s in flat_b if s.get("chunk_id") not in {x.get("chunk_id") for x in flat_a}]
        else:
            merged = flat_a + flat_b
        if dedup:
            seen: set[str] = set()
            unique = []
            for s in merged:
                cid = s.get("chunk_id", "")
                if cid not in seen:
                    seen.add(cid); unique.append(s)
            merged = unique
        return {"candidates": merged}

    async def _run_cache_check(self, params: dict, inputs: dict) -> dict:
        return {"query": inputs["query"]}

    async def _run_ab_test(self, params: dict, inputs: dict) -> dict:
        ratio_a = float(params.get("ratio_a", 0.5))
        query = inputs["query"]
        go_a = random.random() < ratio_a
        return {"query_a": query if go_a else "", "query_b": "" if go_a else query}

    async def _run_feedback_loop(self, params: dict, inputs: dict) -> dict:
        flat = [s for lst in inputs["candidates"] for s in lst]
        return {"candidates": flat}


def _mmr(docs: list[dict], q_emb: list[float], lam: float, top_k: int) -> list[dict]:
    import numpy as np
    def _emb(d: dict) -> list[float]:
        return d.get("embedding") or [0.0] * len(q_emb)
    q = np.array(q_emb, dtype=float)
    embs = [np.array(_emb(d), dtype=float) for d in docs]
    def cos(a: "np.ndarray", b: "np.ndarray") -> float:
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        return float(np.dot(a, b) / (na * nb)) if na and nb else 0.0
    selected, remaining = [], list(range(len(docs)))
    while remaining and len(selected) < top_k:
        scores = []
        for i in remaining:
            rel = cos(embs[i], q)
            div = max((cos(embs[i], embs[j]) for j in selected), default=0.0)
            scores.append((lam * rel - (1 - lam) * div, i))
        _, best = max(scores)
        selected.append(best)
        remaining.remove(best)
    return [docs[i] for i in selected]
