"""
CrewAI multi-agent crews for aerospace process analysis.

Crew 1 — ECO Change Review:
  SpecRetriever → ComplianceAnalyst → ChangeImpactAssessor → ReportWriter

Crew 2 — New-Employee Training Q&A:
  TeachingAgent → GradingAgent → CoachingAgent

Dual-mode: when crewai is installed, real CrewAI runs; otherwise a lightweight
mock calls the same backend REST APIs and produces a structured result dict.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")

_HEADERS = {"X-API-Key": BACKEND_API_KEY} if BACKEND_API_KEY else {}


# ─── Shared tool implementations ─────────────────────────────────────────────

def _post(path: str, body: dict) -> dict:
    r = httpx.post(f"{BACKEND_URL}{path}", json=body, headers=_HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _get(path: str, params: dict | None = None) -> dict:
    r = httpx.get(f"{BACKEND_URL}{path}", params=params, headers=_HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def tool_query_knowledge_base(question: str, strategy: str = "graph_augmented") -> str:
    result = _post("/api/query", {"question": question, "strategy": strategy, "top_k": 5})
    return result.get("answer", "")


def tool_search_entities(entity_name: str) -> str:
    result = _get("/api/graph", {"search": entity_name, "limit_sec": 20})
    nodes = result.get("nodes", [])
    return json.dumps([{"id": n.get("id"), "label": n.get("label"), "type": n.get("type")} for n in nodes[:10]])


def tool_check_compliance(component_id: str) -> str:
    result = _post(f"/api/graph/conflict-check?component={component_id}", {})
    return json.dumps(result)


def tool_get_constraint_graph(chunk_id: str) -> str:
    result = _get("/api/graph/expand/section", {"chunk_id": chunk_id, "depth": 2})
    return json.dumps(result)


def tool_find_related_specs(chunk_id: str) -> str:
    result = _get("/api/graph/references", {"chunk_id": chunk_id})
    return json.dumps(result)


def tool_trace_change_history(doc_id: str) -> str:
    try:
        result = _get(f"/api/audit/chain/{doc_id}", {"verify": False})
        return json.dumps(result.get("records", [])[:10])
    except Exception:
        return "[]"


def tool_generate_report(content: str, title: str = "工艺变更评审报告") -> str:
    return json.dumps({"status": "generated", "title": title, "length": len(content)})


# ─── Mock crew runner (no crewai dependency) ────────────────────────────────

class _AgentResult:
    def __init__(self, role: str, output: str):
        self.role = role
        self.raw = output


def _run_eco_review_mock(eco_number: str, description: str) -> dict:
    """Sequential mock that replicates the 4-agent pipeline."""
    # Agent 1: Retriever
    retrieval = tool_query_knowledge_base(
        f"哪些工艺章节涉及变更 {eco_number}：{description}"
    )
    related = tool_search_entities(eco_number)

    # Agent 2: Compliance Analyst
    compliance = tool_check_compliance(eco_number)

    # Agent 3: Change Impact Assessor
    history: list[dict] = []
    try:
        history = json.loads(tool_trace_change_history(eco_number))
    except Exception:
        pass

    # Agent 4: Report Writer
    report_body = (
        f"# {eco_number} 变更影响评审报告\n\n"
        f"## 一、受影响章节\n{retrieval}\n\n"
        f"## 二、约束冲突检测\n{compliance}\n\n"
        f"## 三、历史变更追踪\n共 {len(history)} 条记录\n\n"
        f"## 四、结论\n请领域专家确认以上影响范围后批准 ECO。"
    )
    tool_generate_report(report_body, title=f"{eco_number} 评审报告")

    return {
        "eco_number": eco_number,
        "affected_sections_summary": retrieval[:300],
        "compliance_conflicts": json.loads(compliance).get("conflict_count", 0),
        "history_records": len(history),
        "report": report_body,
    }


def _run_training_qa_mock(section_chunk_id: str, student_answer: str) -> dict:
    """3-agent training Q&A mock."""
    # Agent 1: Teaching — fetch section and generate question
    context = tool_get_constraint_graph(section_chunk_id)
    question = tool_query_knowledge_base(
        f"从章节 {section_chunk_id} 出一道工艺检验题"
    )

    # Agent 2: Grading — score the student's answer
    score_prompt = (
        f"标准参考：{question[:200]}\n"
        f"学员回答：{student_answer}\n"
        "请打分（0-100）并说明理由。"
    )
    grade = tool_query_knowledge_base(score_prompt)

    # Agent 3: Coaching — targeted chapter guidance
    guidance = tool_query_knowledge_base(
        f"针对学员回答错误的地方，指出需要复习的章节和知识点。学员回答：{student_answer}"
    )

    return {
        "question":  question,
        "grade":     grade,
        "guidance":  guidance,
        "context_nodes": len(json.loads(context).get("nodes", [])) if context else 0,
    }


# ─── CrewAI mode ─────────────────────────────────────────────────────────────

def _run_eco_review_crewai(eco_number: str, description: str) -> dict:
    from crewai import Agent, Crew, Process, Task
    from crewai.tools import tool as crewai_tool

    @crewai_tool("query_knowledge_base")
    def kb_tool(question: str) -> str:
        """Search the aviation process knowledge base."""
        return tool_query_knowledge_base(question)

    @crewai_tool("check_compliance")
    def compliance_tool(component_id: str) -> str:
        """Check constraint conflicts for a component."""
        return tool_check_compliance(component_id)

    @crewai_tool("trace_change_history")
    def history_tool(doc_id: str) -> str:
        """Trace blockchain-backed change history for a document."""
        return tool_trace_change_history(doc_id)

    @crewai_tool("generate_report")
    def report_tool(content: str) -> str:
        """Generate a formal review report from analysis content."""
        return tool_generate_report(content)

    retriever = Agent(
        role="工艺规范检索员",
        goal="找出与 ECO 变更相关的所有工艺章节",
        tools=[kb_tool],
        llm="anthropic/claude-sonnet-4-6",
    )
    analyst = Agent(
        role="约束合规分析师",
        goal="检测约束冲突并评估合规风险",
        tools=[compliance_tool],
        llm="anthropic/claude-sonnet-4-6",
    )
    assessor = Agent(
        role="变更影响评估员",
        goal="追踪下游规范并评估变更影响范围",
        tools=[history_tool],
        llm="anthropic/claude-sonnet-4-6",
    )
    writer = Agent(
        role="报告撰写员",
        goal="撰写完整的工艺变更评审报告",
        tools=[report_tool],
        llm="anthropic/claude-sonnet-4-6",
    )

    crew = Crew(
        agents=[retriever, analyst, assessor, writer],
        tasks=[
            Task(description=f"检索受 ECO {eco_number} 影响的工艺章节。描述：{description}", agent=retriever, expected_output="受影响章节列表"),
            Task(description=f"对 {eco_number} 执行约束冲突检测", agent=analyst, expected_output="冲突报告 JSON"),
            Task(description=f"追踪 {eco_number} 的下游规范和历史变更", agent=assessor, expected_output="影响范围摘要"),
            Task(description="整合前三个 Agent 的分析，输出正式评审报告", agent=writer, expected_output="Markdown 格式评审报告"),
        ],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff()
    return {"eco_number": eco_number, "report": str(result)}


# ─── Public API ───────────────────────────────────────────────────────────────

def run_eco_change_review(eco_number: str, description: str = "") -> dict:
    """Entry point for ECO change review crew."""
    try:
        import crewai  # noqa: F401
        log.info("Running ECO review with real CrewAI")
        return _run_eco_review_crewai(eco_number, description)
    except ImportError:
        log.info("crewai not installed — using mock pipeline")
        return _run_eco_review_mock(eco_number, description)


def run_training_qa(section_chunk_id: str, student_answer: str = "") -> dict:
    """Entry point for new-employee training Q&A crew."""
    return _run_training_qa_mock(section_chunk_id, student_answer)
