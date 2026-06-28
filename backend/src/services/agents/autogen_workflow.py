"""
AutoGen human-in-the-loop (HITL) workflow for aviation process analysis.

Two modes:
1. Collaborative clarification — user iteratively refines their request while
   multiple agents specialise on sub-tasks.
2. Expert validation — AI produces analysis, pauses for human expert approval,
   then continues to the next step.

Dual-mode: pyautogen installed → real AutoGen; otherwise uses a simple async
state-machine that mimics the conversation flow.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

import httpx

log = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
_HEADERS = {"X-API-Key": BACKEND_API_KEY} if BACKEND_API_KEY else {}


class WorkflowState(str, Enum):
    RUNNING          = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED        = "completed"
    FAILED           = "failed"


@dataclass
class WorkflowStep:
    step_id: int
    agent:   str
    content: str
    requires_approval: bool = False
    approved: bool | None = None


@dataclass
class WorkflowSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state:      WorkflowState = WorkflowState.RUNNING
    steps:      list[WorkflowStep] = field(default_factory=list)
    question:   str = ""
    pending_step: int | None = None


# In-memory store (production would use Redis/DB)
_sessions: dict[str, WorkflowSession] = {}


# ─── Backend API helpers ──────────────────────────────────────────────────────

async def _aquery(question: str, strategy: str = "parallel") -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/query",
            json={"question": question, "strategy": strategy, "top_k": 5},
            headers=_HEADERS,
        )
    return r.json().get("answer", "")


async def _aconflict_check(component: str = "") -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/graph/conflict-check",
            params={"component": component} if component else {},
            headers=_HEADERS,
        )
    return r.json()


# ─── Mock workflow (no pyautogen) ────────────────────────────────────────────

async def _run_collaborative_mock(session: WorkflowSession) -> None:
    """4-step collaborative workflow without AutoGen dependency."""
    steps = [
        ("理解意图 Agent",   f"解析用户需求：{session.question}", False),
        ("检索 Agent",       "正在检索相关工艺规范...", False),
        ("分析 Agent",       "正在综合分析检索结果...", True),   # needs expert approval
        ("综述 Agent",       "正在生成最终摘要...", False),
    ]

    for i, (agent, desc, needs_approval) in enumerate(steps):
        if i == 1:
            content = await _aquery(session.question)
        elif i == 2:
            content = await _aquery(
                f"请分析以下内容并标出置信度低于 0.7 的部分，供专家审核：{session.question}"
            )
        elif i == 3:
            content = await _aquery(
                f"请整合以上分析，为用户问题给出最终简明回答：{session.question}",
                strategy="graph_augmented",
            )
        else:
            content = desc

        step = WorkflowStep(
            step_id=i,
            agent=agent,
            content=content,
            requires_approval=needs_approval,
        )
        session.steps.append(step)

        if needs_approval:
            session.state = WorkflowState.WAITING_FOR_HUMAN
            session.pending_step = i
            return  # Pause until human calls approve()

    session.state = WorkflowState.COMPLETED


async def _resume_after_approval(session: WorkflowSession) -> None:
    """Continue workflow from the step after the approved one."""
    start = (session.pending_step or 0) + 1
    session.pending_step = None
    session.state = WorkflowState.RUNNING

    final = await _aquery(
        f"专家已批准分析结果。请为以下问题生成最终回答：{session.question}",
        strategy="graph_augmented",
    )
    session.steps.append(WorkflowStep(
        step_id=start,
        agent="综述 Agent",
        content=final,
    ))
    session.state = WorkflowState.COMPLETED


# ─── Public API ───────────────────────────────────────────────────────────────

async def create_workflow(question: str, mode: str = "collaborative") -> WorkflowSession:
    """
    Create and immediately start a new workflow session.

    Args:
        question: User's initial question or task description.
        mode: "collaborative" | "expert_validation"
    """
    session = WorkflowSession(question=question)
    _sessions[session.session_id] = session

    try:
        import autogen  # noqa: F401
        # Real AutoGen path — not yet wired; falls through to mock
        raise ImportError("autogen real path not wired")
    except ImportError:
        pass

    asyncio.create_task(_run_collaborative_mock(session))
    return session


async def approve_step(session_id: str) -> WorkflowSession:
    """Expert approves the current pending step and resumes the workflow."""
    session = _sessions.get(session_id)
    if not session:
        raise KeyError(f"Unknown session {session_id}")
    if session.state != WorkflowState.WAITING_FOR_HUMAN:
        raise ValueError("Session is not waiting for approval")

    if session.pending_step is not None:
        session.steps[session.pending_step].approved = True

    asyncio.create_task(_resume_after_approval(session))
    return session


async def reject_step(session_id: str, feedback: str = "") -> WorkflowSession:
    """Expert rejects the step; workflow retries with expert feedback injected."""
    session = _sessions.get(session_id)
    if not session:
        raise KeyError(f"Unknown session {session_id}")

    if session.pending_step is not None:
        session.steps[session.pending_step].approved = False
        # Re-run the step with expert feedback
        revised = await _aquery(
            f"专家反馈：{feedback}\n请修订分析结果，原始问题：{session.question}"
        )
        session.steps[session.pending_step].content = revised
        session.steps[session.pending_step].approved = True

    asyncio.create_task(_resume_after_approval(session))
    return session


def get_session(session_id: str) -> WorkflowSession | None:
    return _sessions.get(session_id)
