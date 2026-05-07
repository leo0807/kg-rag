"""多跳推理 Agent，使用 LangGraph 实现。"""
import logging
import operator
from typing import Annotated, TypedDict

try:
    from langgraph.graph import StateGraph, END
except ImportError:  # pragma: no cover - 可选依赖
    StateGraph = None
    END = None
from ..ai.llm_service import get_llm_service
from .multi_hop_support import (
    MAX_HOPS,
    build_decompose_prompt,
    build_doc_aware_sub_queries,
    fallback_parallel_answer,
    _looks_like_bad_sub_queries,
    parse_sub_queries,
    retrieve_for_subquery,
    synthesize_answer as synthesize_multi_hop_answer,
)

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    question: str
    sub_queries: list[str]
    retrieved: Annotated[list[dict], operator.add]
    hop_count: int
    final_answer: str
    steps: Annotated[list[dict], operator.add]

def decompose_question(state: AgentState) -> AgentState:
    doc_aware_sub_queries = build_doc_aware_sub_queries(state["question"])
    if doc_aware_sub_queries:
        sub_queries = doc_aware_sub_queries
    else:
        prompt = build_decompose_prompt(state["question"])
        try:
            content = get_llm_service().chat([{"role": "user", "content": prompt}], timeout=30)
            sub_queries = parse_sub_queries(content, state["question"])
            if _looks_like_bad_sub_queries(sub_queries, state["question"]):
                sub_queries = [state["question"]]
        except Exception as e:
            logger.warning("问题分解失败，使用原问题: %s", e)
            sub_queries = [state["question"]]

    logger.info("问题分解: %d 个子问题", len(sub_queries))
    return {**state, "sub_queries": sub_queries, "hop_count": 0}


def _retrieve_step(state: AgentState, driver, top_k: int = 5) -> AgentState:
    if state["hop_count"] >= len(state["sub_queries"]):
        return state

    current_query = state["sub_queries"][state["hop_count"]]
    logger.info("第 %d 跳检索: %s", state["hop_count"] + 1, current_query)
    retrieved = retrieve_for_subquery(current_query, driver, top_k=top_k)

    step = {
        "hop": state["hop_count"] + 1,
        "query": current_query,
        "found": len(retrieved),
        "titles": [r.get("title", "") for r in retrieved[:3]],
    }

    return {
        **state,
        "retrieved": retrieved,
        "hop_count": state["hop_count"] + 1,
        "steps": [step],
    }


def should_continue(state: AgentState) -> str:
    if state["hop_count"] >= MAX_HOPS:
        logger.warning("达到最大跳数限制 (%d)，强制终止", MAX_HOPS)
        return "synthesize"
    if state["hop_count"] < len(state["sub_queries"]):
        return "retrieve"
    return "synthesize"


def synthesize_answer(state: AgentState) -> AgentState:
    answer, sources, _steps = synthesize_multi_hop_answer(
        state["question"],
        state["retrieved"],
        state["sub_queries"],
    )
    return {**state, "final_answer": answer, "retrieved": sources}


def build_multi_hop_graph(driver, top_k: int = 5):
    if StateGraph is None or END is None:
        raise RuntimeError("langgraph 未安装，无法执行 multi_hop 策略")

    def retrieve(state):
        return _retrieve_step(state, driver, top_k=top_k)

    graph = StateGraph(AgentState)
    graph.add_node("decompose",  decompose_question)
    graph.add_node("retrieve",   retrieve)
    graph.add_node("synthesize", synthesize_answer)

    graph.set_entry_point("decompose")
    graph.add_edge("decompose", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        should_continue,
        {"retrieve": "retrieve", "synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", END)

    return graph.compile()


def _run_multi_hop(question: str, driver, top_k: int = 5) -> tuple[str, list[dict], list[dict]]:
    graph = build_multi_hop_graph(driver, top_k=top_k)
    initial_state = AgentState(
        question=question,
        sub_queries=[],
        retrieved=[],
        hop_count=0,
        final_answer="",
        steps=[],
    )
    result = graph.invoke(initial_state)
    seen: set[str] = set()
    sources: list[dict] = []
    for r in result.get("retrieved", []):
        if r["chunk_id"] in seen:
            continue
        sources.append(r)
        seen.add(r["chunk_id"])
    return result.get("final_answer", ""), sources[: top_k * 2], result.get("steps", [])


def multi_hop_search(question: str, driver, top_k: int = 5) -> tuple[str, list[dict], list[dict], str]:
    try:
        answer, sources, steps = _run_multi_hop(question, driver, top_k=top_k)
        if not answer or not sources:
            raise ValueError("多跳推理无结果")
        return answer, sources, steps, "multi_hop"
    except Exception as e:
        logger.warning("multi_hop降级到parallel_rrf: %s", e)
        answer, sources, steps = fallback_parallel_answer(question, driver, top_k=top_k)
        return answer, sources, steps, "parallel_rrf_fallback"


async def multi_hop_query_stream(question: str, driver, top_k: int = 5):
    import asyncio

    try:
        graph = build_multi_hop_graph(driver, top_k=top_k)
        initial_state = AgentState(
            question=question,
            sub_queries=[],
            retrieved=[],
            hop_count=0,
            final_answer="",
            steps=[],
        )
        seen_chunk_ids = set()
        async for output in graph.astream(initial_state):
            node_name = list(output.keys())[0]
            data = output[node_name]

            if node_name == "decompose":
                queries = data.get("sub_queries", [])
                yield {"type": "status", "content": f"🔍 问题已分解为 {len(queries)} 个步骤"}
                yield {"type": "steps", "content": [{"hop": 0, "query": "分解问题", "sub_queries": queries}]}

            elif node_name == "retrieve":
                hop = data.get("hop_count", 0)
                steps = data.get("steps", [])
                if steps:
                    yield {"type": "status", "content": f"📖 正在执行第 {hop} 步检索..."}
                    yield {"type": "steps", "content": steps}
                
                # 提取新发现的来源
                new_retrieved = data.get("retrieved", [])
                new_sources = []
                for s in new_retrieved:
                    if s["chunk_id"] not in seen_chunk_ids:
                        new_sources.append({
                            "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                            "number":   s.get("number") or "", "title": s.get("title") or "",
                            "score":    round(float(s.get("score", 0)), 4),
                        })
                        seen_chunk_ids.add(s["chunk_id"])
                
                if new_sources:
                    yield {"type": "sources", "content": new_sources}

            elif node_name == "synthesize":
                yield {"type": "status", "content": "✨ 正在综合多步检索结果..."}
                answer = data.get("final_answer", "")
                if answer:
                    for char in answer:
                        yield {"type": "delta", "content": char}
                        await asyncio.sleep(0.005)

        yield {"type": "done", "content": None}
    except Exception as e:
        logger.warning("多跳流式查询失败，降级到 parallel_rrf: %s", e)
        answer, sources, steps = fallback_parallel_answer(question, driver, top_k=top_k)
        if steps:
            yield {"type": "steps", "content": steps}
        if sources:
            yield {
                "type": "sources",
                "content": [
                    {
                        "chunk_id": s["chunk_id"],
                        "doc_id": s["doc_id"],
                        "number": s.get("number") or "",
                        "title": s.get("title") or "",
                        "score": round(float(s.get("score", 0)), 4),
                    }
                    for s in sources
                ],
            }
        for char in answer:
            yield {"type": "delta", "content": char}
            await asyncio.sleep(0.005)
        yield {"type": "done", "content": None}


def multi_hop_query(question: str, driver, top_k: int = 5) -> tuple[str, list[dict], list[dict]]:
    answer, sources, steps, _strategy = multi_hop_search(question, driver, top_k=top_k)
    return answer, sources, steps
