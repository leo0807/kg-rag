"""
src/services/multi_hop.py
多跳推理 Agent，使用 LangGraph 实现
"""
import logging
from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END
from ..core.config import settings

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
    import requests

    prompt = f"""你是一个航空工艺规范专家。请分析以下问题，判断是否需要多步检索才能回答。

问题：{state['question']}

如果问题涉及多个文档之间的关联（比如"A文档引用的B文档里的内容"），
请将其分解为2-3个子问题，每个子问题可以独立检索。

如果问题可以直接检索回答，只输出原问题本身。

只输出子问题列表，每行一个问题，不要有编号或其他内容。"""

    try:
        res = requests.post(
            f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":    settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        content    = res.json()["choices"][0]["message"]["content"]
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
        from .embedder     import embed_query
        from .milvus_store import search_sections
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
                               s.content  AS content
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
    import requests

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
        f"[{r['doc_id']} §{r['number']}] {r['title']}\n{r.get('content', '')}"
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
        res = requests.post(
            f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":    settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        answer = res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("多跳综合失败: %s", e)
        answer = f"根据多步检索，找到 {len(unique)} 个相关章节：\n\n{context[:2000]}"

    return {**state, "final_answer": answer}


def build_multi_hop_graph(driver):
    """构建多跳推理图"""

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
