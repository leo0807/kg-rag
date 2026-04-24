"""
src/services/multi_hop.py
多跳推理 Agent，使用 LangGraph 实现
"""
import logging
from typing import TypedDict, Annotated
import operator
try:
    from langgraph.graph import StateGraph, END
except ImportError:  # pragma: no cover - 可选依赖
    StateGraph = None
    END = None
from ..ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)

MAX_HOPS = 5  # 最大迭代次数，防止死循环


# ── Agent 状态定义 ────────────────────────────────────────────
class AgentState(TypedDict):
    question:    str
    sub_queries: list[str]
    retrieved:   Annotated[list[dict], operator.add]  # 累积检索结果
    hop_count:   int
    final_answer: str
    steps:       Annotated[list[dict], operator.add]  # 中间推理步骤


# ── 节点函数 ──────────────────────────────────────────────────

def decompose_question(state: AgentState) -> AgentState:
    """
    第一跳：把复杂问题分解成子问题
    """
    prompt = f"""你是一个航空工艺规范专家。请分析以下问题，判断是否需要多步检索才能回答。

问题：{state['question']}

如果问题涉及多个文档之间的关联（比如"A文档引用的B文档里的内容"），
请将其分解为2-3个子问题，每个子问题可以独立检索。

如果问题可以直接检索回答，只输出原问题本身。

只输出子问题列表，每行一个问题，不要有编号或其他内容。"""

    try:
        content     = get_llm_service().chat(
            [{"role": "user", "content": prompt}], timeout=30
        )
        sub_queries = [q.strip() for q in content.strip().split("\n") if q.strip()]
    except Exception as e:
        logger.warning("问题分解失败，使用原问题: %s", e)
        sub_queries = [state["question"]]

    logger.info("问题分解: %d 个子问题", len(sub_queries))
    return {**state, "sub_queries": sub_queries, "hop_count": 0}


def retrieve_for_subquery(state: AgentState, driver, top_k: int = 3) -> AgentState:
    """
    每跳检索：对当前子问题进行检索
    """
    if state["hop_count"] >= len(state["sub_queries"]):
        return state

    current_query = state["sub_queries"][state["hop_count"]]
    logger.info("第 %d 跳检索: %s", state["hop_count"] + 1, current_query)

    retrieved = []

    # 全文检索
    try:
        with driver.session() as session:
            result = session.run("""
                CALL db.index.fulltext.queryNodes(
                    'cps_fulltext_index', $question
                ) YIELD node, score
                RETURN node.chunk_id AS chunk_id,
                       node.doc_id   AS doc_id,
                       node.number   AS number,
                       node.title    AS title,
                       node.content  AS content,
                       score
                ORDER BY score DESC
                LIMIT $top_k
            """, question=current_query, top_k=top_k)
            retrieved = [dict(r) for r in result]
    except Exception as e:
        logger.warning("多跳全文检索失败: %s", e)

    # 向量检索补充
    try:
        from .embedder import embed_query
        from ..storage.milvus_store import search_sections
        vec_results = search_sections(embed_query(current_query), top_k=top_k)
        seen = {r["chunk_id"] for r in retrieved}
        for r in vec_results:
            if r["chunk_id"] not in seen:
                with driver.session() as session:
                    node = session.run("""
                        MATCH (s:Section {chunk_id: $cid})
                        RETURN s.chunk_id AS chunk_id,
                               s.doc_id   AS doc_id,
                               s.number   AS number,
                               s.title    AS title,
                               s.content  AS content,
                               s.page_idx AS page_idx,
                               s.bbox     AS bbox
                    """, cid=r["chunk_id"]).single()
                    if node:
                        retrieved.append({**dict(node), "score": r["score"]})
                seen.add(r["chunk_id"])
    except Exception as e:
        logger.warning("多跳向量检索失败: %s", e)

    # 记录中间步骤
    step = {
        "hop":    state["hop_count"] + 1,
        "query":  current_query,
        "found":  len(retrieved),
        "titles": [r.get("title", "") for r in retrieved[:3]],
    }

    return {
        **state,
        "retrieved": retrieved,
        "hop_count": state["hop_count"] + 1,
        "steps":     [step],
    }


def should_continue(state: AgentState) -> str:
    """判断是否需要继续检索，加入最大跳数保护"""
    if state["hop_count"] >= MAX_HOPS:
        logger.warning("达到最大跳数限制 (%d)，强制终止", MAX_HOPS)
        return "synthesize"
    if state["hop_count"] < len(state["sub_queries"]):
        return "retrieve"
    return "synthesize"


def synthesize_answer(state: AgentState) -> AgentState:
    """综合所有检索结果生成最终答案"""
    if not state["retrieved"]:
        return {**state, "final_answer": "在知识库中未找到相关章节，请确认文件已入库。"}

    # 去重
    seen   = set()
    unique = []
    for r in state["retrieved"]:
        if r["chunk_id"] not in seen:
            unique.append(r)
            seen.add(r["chunk_id"])

    context = "\n\n".join(
        f"[{r['doc_id']} §{r['number']} (第{r.get('page_idx', 0)+1}页)] {r['title']}\n{r.get('content', '')}"
        for r in unique[:6]
    )

    prompt = f"""你是一个航空制造工艺规范专家助手。请根据以下多步检索到的工艺规范内容，回答用户的问题。

## 检索到的规范内容

{context}

## 原始问题

{state['question']}

## 子问题分解

{chr(10).join(f'- {q}' for q in state['sub_queries'])}

## 回答要求
1. 综合多个检索结果，给出完整回答
2. 只根据规范内容回答，标注来源章节
3. 如果某个子问题没有找到答案，请说明

请回答："""

    try:
        answer = get_llm_service().chat(
            [{"role": "user", "content": prompt}], timeout=60
        )
    except Exception as e:
        logger.warning("多跳综合失败: %s", e)
        answer = f"根据多步检索，找到 {len(unique)} 个相关章节：\n\n{context[:2000]}"

    return {**state, "final_answer": answer}


def build_multi_hop_graph(driver):
    """构建多跳推理图"""
    if StateGraph is None or END is None:
        raise RuntimeError("langgraph 未安装，无法执行 multi_hop 策略")

    def retrieve(state):
        return retrieve_for_subquery(state, driver)

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


async def multi_hop_query_stream(question: str, driver, top_k: int = 5):
    """
    流式多跳推理查询入口，用于前端可视化 CoT 过程。
    Yields: {"type": "status"|"steps"|"sources"|"delta"|"done", "content": ...}
    """
    import asyncio
    graph = build_multi_hop_graph(driver)

    initial_state = AgentState(
        question     = question,
        sub_queries  = [],
        retrieved    = [],
        hop_count    = 0,
        final_answer = "",
        steps        = [],
    )

    # 由于 LangGraph invoke 是同步的，我们在 thread pool 运行
    # 为了实现真正的流式，我们可能需要更复杂的观察者模式，
    # 这里我们先通过 graph.stream() 捕获节点切换
    
    seen_chunk_ids = set()
    
    try:
        # 使用 graph.astream() 进行异步流式处理
        async for output in graph.astream(initial_state):
            # output 是一个 dict，key 是节点名，value 是该节点返回的状态增量
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
                    # 模拟打字机流式输出（因为 synthesize 是一次性生成的）
                    for char in answer:
                        yield {"type": "delta", "content": char}
                        await asyncio.sleep(0.005)

        yield {"type": "done", "content": None}

    except Exception as e:
        logger.error("多跳流式查询异常: %s", e)
        yield {"type": "error", "content": str(e)}


def multi_hop_query(question: str, driver, top_k: int = 5) -> tuple[str, list[dict], list[dict]]:
    """
    多跳推理查询入口
    返回：(answer, sources, steps)
    """
    graph = build_multi_hop_graph(driver)

    initial_state = AgentState(
        question     = question,
        sub_queries  = [],
        retrieved    = [],
        hop_count    = 0,
        final_answer = "",
        steps        = [],
    )

    result = graph.invoke(initial_state)

    # 去重来源
    seen    = set()
    sources = []
    for r in result["retrieved"]:
        if r["chunk_id"] not in seen:
            sources.append(r)
            seen.add(r["chunk_id"])

    return result["final_answer"], sources[:top_k], result.get("steps", [])
