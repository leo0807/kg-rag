from __future__ import annotations

import json
import logging
import re

from .agent_helpers import (
    build_compare_plan,
    collect_tool_outputs,
    compose_compare_answer,
    dedupe_images,
    dedupe_sections,
    is_compare_question,
    summarize_sources,
)
from .tools import TOOLS

logger = logging.getLogger(__name__)


class AgentExecutor:
    MAX_ITERATIONS = 5

    def __init__(self, llm_service, tool_executor):
        self.llm = llm_service
        self.tools = tool_executor

    async def run(self, question: str, emit_event=None) -> dict:
        compare_mode = is_compare_question(question)
        compare_plan = build_compare_plan(question) if compare_mode else []
        messages = [
            {
                "role": "system",
                "content": """你是COMAC航空工艺规范专家助手。
通过调用工具检索工艺规范，回答用户问题。

工作原则：
1. 先分析问题类型（查询/比较/追溯）
2. 比较类问题要分别检索每个规范的章节，再综合对比
3. 工艺操作类问题优先检索章节，必要时再查图片
4. 答案不完整时继续调用工具补充，不要过早结束
5. 收集足够信息后调用 final_answer
6. 引用时必须标注规范编号和章节号

比较题执行顺序：
1. 先查第一个规范的相关章节
2. 再查第二个规范的相关章节
3. 如有需要再查相关图片
4. 最后综合生成答案""",
            },
            {"role": "user", "content": question},
        ]

        all_sources: list[dict] = []
        all_images: list[dict] = []
        agent_steps: list[dict] = []

        async def _emit_step(payload: dict) -> None:
            agent_steps.append(payload)
            if emit_event:
                await emit_event(payload)

        for iteration in range(self.MAX_ITERATIONS):
            logger.info(
                "[agent] iteration=%s compare_mode=%s sources=%s images=%s",
                iteration + 1,
                compare_mode,
                len(all_sources),
                len(all_images),
            )

            if compare_mode and iteration < len(compare_plan):
                response = {"text": "", "tool_use": compare_plan[iteration]}
                tool_use = response["tool_use"]
            elif iteration > 0 and all_sources and not compare_mode:
                return {
                    "answer": compose_compare_answer(question, all_sources, all_images=all_images),
                    "sources": all_sources,
                    "images": all_images,
                    "iterations": iteration + 1,
                    "strategy_used": "agent",
                    "agent_steps": agent_steps,
                }
            else:
                response = await self.llm.chat_with_tools(messages=messages, tools=TOOLS)
                tool_use = response.get("tool_use")
                if not tool_use:
                    tool_use = self._fallback_tool_use(question, all_sources, iteration)
                    if tool_use:
                        response = {**response, "tool_use": tool_use}

            if not tool_use:
                text = response.get("text", "")
                if all_sources:
                    text = compose_compare_answer(question, all_sources, all_images=all_images)
                return {
                    "answer": text or summarize_sources(all_sources),
                    "sources": all_sources,
                    "images": all_images,
                    "iterations": iteration + 1,
                    "strategy_used": "agent",
                    "agent_steps": agent_steps,
                }

            tool_name = tool_use.get("name", "")
            tool_input = tool_use.get("input", {}) or {}
            logger.info(
                "[agent] tool_call iteration=%s tool=%s input=%s",
                iteration + 1,
                tool_name,
                tool_input,
            )

            if tool_name == "final_answer":
                await _emit_step(
                    {
                        "type": "agent_step",
                        "step": iteration + 1,
                        "action": "生成最终答案",
                        "status": "done",
                    }
                )
                answer = tool_input.get("answer", response.get("text", ""))
                citations = tool_input.get("citations", [])
                return {
                    "answer": answer or summarize_sources(all_sources),
                    "sources": all_sources,
                    "images": all_images,
                    "citations": citations,
                    "iterations": iteration + 1,
                    "strategy_used": "agent",
                    "agent_steps": agent_steps,
                }

            await _emit_step(
                {
                    "type": "agent_step",
                    "step": iteration + 1,
                    "action": f"调用工具：{tool_name}",
                    "input": tool_input,
                    "status": "running",
                }
            )
            tool_result = await self.tools.execute(tool_name, tool_input)
            added_sections, added_images = collect_tool_outputs(tool_name, tool_result)
            if added_sections:
                all_sources = dedupe_sections(all_sources + added_sections)
            if added_images:
                all_images = dedupe_images(all_images + added_images)

            result_summary = "工具调用完成"
            if isinstance(tool_result, dict):
                if "sections" in tool_result:
                    result_summary = f"找到 {len(tool_result.get('sections', []))} 个相关章节"
                elif tool_name == "compare_documents":
                    result_summary = (
                        f"完成跨文档对比检索，章节 {len(added_sections)} 个，"
                        f"图片 {len(added_images)} 张"
                    )
                elif tool_name == "search_images":
                    result_summary = f"找到 {len(tool_result.get('images', []))} 张相关图片"

            await _emit_step(
                {
                    "type": "agent_step",
                    "step": iteration + 1,
                    "action": f"工具 {tool_name} 完成",
                    "result_summary": result_summary,
                    "status": "done",
                }
            )

            if compare_mode and tool_name == "compare_documents":
                answer = compose_compare_answer(
                    question,
                    all_sources,
                    comparison=tool_result,
                    all_images=all_images,
                )
                return {
                    "answer": answer,
                    "sources": all_sources,
                    "images": all_images,
                    "iterations": iteration + 1,
                    "strategy_used": "agent",
                    "agent_steps": agent_steps,
                }

            messages.append(
                {
                    "role": "assistant",
                    "content": response.get("text", ""),
                    "tool_calls": [
                        {
                            "id": tool_use.get("id", f"call_{iteration}"),
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_input, ensure_ascii=False),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_use.get("id", f"call_{iteration}"),
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        return {
            "answer": compose_compare_answer(question, all_sources, all_images=all_images),
            "sources": all_sources,
            "images": all_images,
            "iterations": self.MAX_ITERATIONS,
            "strategy_used": "agent",
            "agent_steps": agent_steps,
        }

    def _fallback_tool_use(self, question: str, sources: list[dict], iteration: int) -> dict | None:
        doc_ids = re.findall(r"CPS\d{3,4}", question.upper())
        compare_words = ("不同", "差异", "区别", "比较", "有什么不同")
        if len(doc_ids) >= 2 and any(word in question for word in compare_words):
            topic = re.sub(r"CPS\d{3,4}", "", question)
            topic = re.sub(r"[和与及,，。？?比较不同差异区别有什么]", " ", topic)
            topic = re.sub(r"\s+", " ", topic).strip() or "相关要求"
            if iteration == 0:
                return {
                    "name": "search_sections",
                    "input": {"query": topic, "doc_id": doc_ids[0], "top_k": 5},
                }
            if iteration == 1:
                return {
                    "name": "search_sections",
                    "input": {"query": topic, "doc_id": doc_ids[1], "top_k": 5},
                }
            if iteration == 2:
                return {
                    "name": "compare_documents",
                    "input": {
                        "doc_id_a": doc_ids[0],
                        "doc_id_b": doc_ids[1],
                        "topic": topic,
                    },
                }
        if doc_ids:
            section_match = re.search(r"§?\s*([\d.]+)", question)
            if section_match:
                return {
                    "name": "get_section_content",
                    "input": {
                        "doc_id": doc_ids[0],
                        "section_number": section_match.group(1),
                    },
                }
            if iteration == 0 and not sources:
                return {
                    "name": "search_sections",
                    "input": {
                        "query": question,
                        "doc_id": doc_ids[0],
                        "top_k": 5,
                    },
            }
        if iteration == 0 and not sources:
            return {
                "name": "search_sections",
                "input": {"query": question, "top_k": 5},
            }
        return None
