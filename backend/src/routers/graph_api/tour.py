"""
src/routers/graph_tour.py
图谱导览（Graph Tour）相关 API：AI 自动规划路径 + 流式讲解
"""
import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from neo4j import Driver
from pydantic import BaseModel

from ...core.database import get_driver
from ...services.ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


async def _stream_explanation(topic: str, node: dict) -> AsyncIterator[str]:
    """为导览节点生成流式 AI 讲解。"""
    type_label = {
        "Section":    "章节",
        "Document":   "文档",
        "Tool":       "工具/设备",
        "Material":   "材料",
        "Process":    "工艺工序",
        "Constraint": "技术约束",
        "Image":      "图表",
    }.get(node.get("type", ""), node.get("type", ""))

    name    = node.get("name") or node.get("id", "")
    content = (node.get("content") or node.get("description") or "")[:400]
    doc_id  = node.get("doc_id", "")

    user_prompt = (
        f"导览主题：「{topic}」\n"
        f"当前节点（{type_label}）：{name}"
        + (f"\n所属文档：{doc_id}" if doc_id else "")
        + (f"\n内容摘要：{content}" if content else "")
        + f"\n\n请用2~3句话介绍该{type_label}在「{topic}」中的作用与重要性，"
          f"语言简洁专业，适合航空工程师快速理解。"
    )

    messages = [
        {"role": "system", "content": "你是航空工艺规范知识库的AI导览员，用简洁专业的语言讲解每个节点的知识要点。"},
        {"role": "user",   "content": user_prompt},
    ]

    try:
        async for delta in get_llm_service().stream_chat(
            messages, max_tokens=180, temperature=0.3, timeout=25
        ):
            yield delta
    except Exception as exc:
        logger.warning("导览LLM调用失败: %s", exc)
        yield f"（{name}：{content[:80]}{'…' if len(content) > 80 else ''}）"


class TourRequest(BaseModel):
    topic:     str
    max_stops: int = 6


@router.post("/graph/tour")
async def graph_tour(
    req:    TourRequest,
    driver: Driver = Depends(get_driver),
):
    """
    图谱漫游：以主题为起点，AI 自动规划导览路径，流式讲解每个节点知识要点。

    SSE 事件格式：
      {"type":"init",  "total":N, "topic":"..."}
      {"type":"path",  "nodes":[...], "edges":[...]}   ← 导览子图
      {"type":"stop",  "index":i, "node_id":"...", "node":{...}}
      {"type":"delta", "content":"..."}                ← 流式AI讲解
      {"type":"next_stop"}                             ← 当前站讲解完毕
      {"type":"done"}
    """
    async def generate():
        # ── ① 检索与主题相关的章节 ──────────────────────────────────────────
        from .query.core import do_retrieval

        loop = asyncio.get_running_loop()
        try:
            sections, _ = await loop.run_in_executor(
                None,
                lambda: do_retrieval(driver, req.topic, "graph_augmented", top_k=10),
            )
        except Exception as exc:
            logger.warning("导览检索失败: %s", exc)
            sections = []

        if not sections:
            yield f'data: {json.dumps({"type":"error","message":"未找到与该主题相关的内容"}, ensure_ascii=False)}\n\n'
            return

        # ── ② 展开子图：章节 → 文档 + 实体邻居 ─────────────────────────────
        tour_nodes: list[dict] = []
        tour_edges: list[dict] = []
        seen_ids:   set[str]   = set()
        chunk_ids = [s["chunk_id"] for s in sections[: req.max_stops + 4]]

        def _add_node(n: dict) -> bool:
            if n["id"] in seen_ids:
                return False
            seen_ids.add(n["id"])
            tour_nodes.append(n)
            return True

        with driver.session() as session:
            rows = session.run("""
                UNWIND $chunk_ids AS cid
                MATCH (s:Section {chunk_id: cid})
                OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(s)
                OPTIONAL MATCH (s)-[:REQUIRES_TOOL]->(t:Tool)
                OPTIONAL MATCH (s)-[:USES_MATERIAL]->(m:Material)
                OPTIONAL MATCH (s)-[:INVOLVES_PROCESS]->(p:Process)
                RETURN
                    s.chunk_id                                   AS cid,
                    COALESCE(s.title, s.chunk_id)                AS sec_name,
                    s.doc_id                                     AS sec_doc,
                    COALESCE(s.content, '')                      AS sec_content,
                    d.name                                       AS doc_id,
                    COALESCE(d.title, d.name)                    AS doc_name,
                    collect(DISTINCT t.name)[0..2]               AS tools,
                    collect(DISTINCT m.name)[0..2]               AS mats,
                    collect(DISTINCT p.name)[0..2]               AS procs
            """, chunk_ids=chunk_ids)

            for row in rows:
                # Section node
                sec_node = {
                    "id":      row["cid"],
                    "name":    row["sec_name"],
                    "type":    "Section",
                    "doc_id":  row["sec_doc"] or "",
                    "content": (row["sec_content"] or "")[:300],
                    "label":   row["sec_name"],
                }
                _add_node(sec_node)

                # Document node
                if row["doc_id"]:
                    doc_node = {
                        "id":    row["doc_id"],
                        "name":  row["doc_name"],
                        "type":  "Document",
                        "doc_id": row["doc_id"],
                        "label": row["doc_name"],
                    }
                    if _add_node(doc_node):
                        tour_edges.append({"source": row["doc_id"], "target": row["cid"], "type": "HAS_SECTION"})

                # Entity nodes
                for names, etype, rel in [
                    (row["tools"], "Tool",     "REQUIRES_TOOL"),
                    (row["mats"],  "Material", "USES_MATERIAL"),
                    (row["procs"], "Process",  "INVOLVES_PROCESS"),
                ]:
                    for name in (names or []):
                        if not name:
                            continue
                        ent = {"id": name, "name": name, "type": etype, "label": name, "doc_id": ""}
                        if _add_node(ent):
                            tour_edges.append({"source": row["cid"], "target": name, "type": rel})

        # ── ③ 确定导览顺序：取前 max_stops 个章节节点 ─────────────────────
        stop_nodes = [
            n for n in tour_nodes
            if n["type"] == "Section" and n["id"] in {s["chunk_id"] for s in sections}
        ][: req.max_stops]

        if not stop_nodes:
            stop_nodes = [n for n in tour_nodes if n["type"] == "Section"][: req.max_stops]

        total = len(stop_nodes)

        # ── ④ 发送初始化帧 ─────────────────────────────────────────────────
        yield f'data: {json.dumps({"type":"init","total":total,"topic":req.topic}, ensure_ascii=False)}\n\n'
        yield f'data: {json.dumps({"type":"path","nodes":tour_nodes,"edges":tour_edges}, ensure_ascii=False)}\n\n'

        # ── ⑤ 逐站发送：stop → delta… → next_stop ──────────────────────
        for i, node in enumerate(stop_nodes):
            yield f'data: {json.dumps({"type":"stop","index":i,"node_id":node["id"],"node":node}, ensure_ascii=False)}\n\n'

            async for delta in _stream_explanation(req.topic, node):
                yield f'data: {json.dumps({"type":"delta","content":delta}, ensure_ascii=False)}\n\n'

            yield f'data: {json.dumps({"type":"next_stop"})}\n\n'

        yield f'data: {json.dumps({"type":"done"})}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/graph/semantic-links")
async def trigger_semantic_links(
    threshold: float = 0.88,
    top_k: int = 5,
    dry_run: bool = False,
    driver: Driver = Depends(get_driver),
):
    """
    触发跨文档语义边构建（离线批处理）。
    可先用 dry_run=true 预览会写入多少条边。
    """
    from ...services.retrieval.semantic_linker import build_semantic_links
    result = build_semantic_links(driver, threshold=threshold, top_k=top_k, dry_run=dry_run)
    return result
