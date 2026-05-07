from __future__ import annotations

import json
import logging
import re

from .tools import TOOLS

logger = logging.getLogger(__name__)


class AgentExecutor:
    MAX_ITERATIONS = 5

    def __init__(self, llm_service, tool_executor):
        self.llm = llm_service
        self.tools = tool_executor

    async def run(self, question: str) -> dict:
        messages = [
            {
                "role": "system",
                "content": """你是COMAC航空工艺规范专家助手。
通过调用工具检索工艺规范，回答用户问题。

工作原则：
1. 先分析问题类型（查询/比较/追溯）
2. 选择合适的工具检索信息
3. 如需多步骤，逐步调用工具
4. 收集足够信息后调用 final_answer
5. 引用时必须标注规范编号和章节号""",
            },
            {"role": "user", "content": question},
        ]

        all_sources: list[dict] = []

        for iteration in range(self.MAX_ITERATIONS):
            if iteration > 0 and all_sources:
                return {
                    "answer": self._compose_answer(question, all_sources),
                    "sources": all_sources,
                    "iterations": iteration + 1,
                    "strategy_used": "agent",
                }
            response = await self.llm.chat_with_tools(messages=messages, tools=TOOLS)
            tool_use = response.get("tool_use")
            if not tool_use:
                tool_use = self._fallback_tool_use(question, all_sources, iteration)
                if tool_use:
                    response = {**response, "tool_use": tool_use}
            if not tool_use:
                text = response.get("text", "")
                if all_sources:
                    text = self._compose_answer(question, all_sources)
                return {
                    "answer": text or self._summarize_sources(question, all_sources),
                    "sources": all_sources,
                    "iterations": iteration + 1,
                    "strategy_used": "agent",
                }

            tool_name = tool_use.get("name", "")
            tool_input = tool_use.get("input", {}) or {}
            if tool_name == "final_answer":
                answer = tool_input.get("answer", response.get("text", ""))
                citations = tool_input.get("citations", [])
                return {
                    "answer": answer or self._summarize_sources(question, all_sources),
                    "sources": all_sources,
                    "citations": citations,
                    "iterations": iteration + 1,
                    "strategy_used": "agent",
                }

            tool_result = await self.tools.execute(tool_name, tool_input)
            if "sections" in tool_result:
                all_sources.extend(tool_result["sections"])
            elif tool_name == "compare_documents":
                for value in tool_result.values():
                    if isinstance(value, list):
                        all_sources.extend(value)

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
            "answer": self._summarize_sources(question, all_sources),
            "sources": all_sources,
            "iterations": self.MAX_ITERATIONS,
            "strategy_used": "agent",
        }

    def _fallback_tool_use(self, question: str, sources: list[dict], iteration: int) -> dict | None:
        doc_ids = re.findall(r"CPS\d{3,4}", question.upper())
        compare_words = ("不同", "差异", "区别", "比较", "有什么不同")
        if len(doc_ids) >= 2 and any(word in question for word in compare_words):
            topic = re.sub(r"CPS\d{3,4}", "", question)
            topic = re.sub(r"[和与及,，。？?比较不同差异区别有什么]", " ", topic)
            topic = re.sub(r"\s+", " ", topic).strip() or "相关要求"
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
                "input": {
                    "query": question,
                    "top_k": 5,
                },
            }
        return None

    def _compose_answer(self, question: str, sources: list[dict]) -> str:
        docs: dict[str, list[dict]] = {}
        for src in sources:
            docs.setdefault(src.get("doc_id", ""), []).append(src)
        if len(docs) >= 2 and any(word in question for word in ("不同", "差异", "区别", "比较")):
            lines = ["根据检索到的规范，对比结果如下："]
            for doc_id, items in list(docs.items())[:2]:
                item = items[0]
                lines.append(
                    f"- {doc_id} §{item.get('number', '')}：{item.get('title', '')}。"
                    f"{(item.get('content') or '')[:180]}"
                )
            return "\n".join(lines)
        return self._summarize_sources(question, sources)

    def _summarize_sources(self, question: str, sources: list[dict]) -> str:
        if not sources:
            return "已达最大推理步数，但未找到足够的相关章节。"
        snippets = []
        for src in sources[:3]:
            snippets.append(
                f"[{src.get('doc_id', '')} §{src.get('number', '')}] {src.get('title', '')}\n"
                f"{(src.get('content') or '')[:200]}"
            )
        return "已达最大推理步数，基于已检索内容：\n\n" + "\n\n".join(snippets)
