"""
Multi-agent orchestration endpoints.

POST /api/agents/eco-review        — CrewAI ECO change-review crew
POST /api/agents/training-qa       — CrewAI new-employee training Q&A
POST /api/agents/workflow          — AutoGen human-in-the-loop workflow
POST /api/agents/workflow/{id}/approve — Expert approves a pending step
POST /api/agents/workflow/{id}/reject  — Expert rejects with feedback
GET  /api/agents/workflow/{id}    — Poll workflow state
POST /api/agents/sk-plan           — Semantic Kernel sequential planner
POST /api/agents/sk-sharepoint-sync — SharePoint → knowledge base sync
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.deps import get_current_user
from ..db.models import User
from ..services.agents.crewai_crews import run_eco_change_review, run_training_qa
from ..services.agents.autogen_workflow import (
    WorkflowSession,
    approve_step,
    create_workflow,
    get_session,
    reject_step,
)
from ..services.agents.semantic_kernel_planner import (
    get_sk_planner,
    sync_sharepoint_to_knowledge_base,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


class ECOReviewRequest(BaseModel):
    eco_number:  str
    description: str = ""


class TrainingQARequest(BaseModel):
    section_chunk_id: str
    student_answer:   str = ""


class WorkflowRequest(BaseModel):
    question: str
    mode:     str = "collaborative"  # collaborative | expert_validation


class RejectRequest(BaseModel):
    feedback: str = ""


class SKPlanRequest(BaseModel):
    goal: str


def _session_to_dict(s: WorkflowSession) -> dict:
    return {
        "session_id": s.session_id,
        "state":      s.state,
        "question":   s.question,
        "pending_step": s.pending_step,
        "steps": [
            {
                "step_id":          st.step_id,
                "agent":            st.agent,
                "content":          st.content[:500],
                "requires_approval": st.requires_approval,
                "approved":         st.approved,
            }
            for st in s.steps
        ],
    }


@router.post("/eco-review")
async def eco_review(
    body: ECOReviewRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Trigger the 4-agent ECO change-review crew.
    Returns a structured report covering affected sections, constraint conflicts,
    downstream spec tracing, and formal review conclusions.
    """
    try:
        result = run_eco_change_review(body.eco_number, body.description)
    except Exception as exc:
        log.error("ECO review failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.post("/training-qa")
async def training_qa(
    body: TrainingQARequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Training Q&A crew: generates a question from the section, grades the
    student's answer, and provides targeted chapter guidance for wrong answers.
    """
    try:
        result = run_training_qa(body.section_chunk_id, body.student_answer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.post("/workflow")
async def start_workflow(
    body: WorkflowRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Start an AutoGen human-in-the-loop workflow session.
    The session may pause at steps requiring expert approval.
    """
    session = await create_workflow(body.question, body.mode)
    return _session_to_dict(session)


@router.get("/workflow/{session_id}")
async def get_workflow(
    session_id: str,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Workflow session not found")
    return _session_to_dict(session)


@router.post("/workflow/{session_id}/approve")
async def approve_workflow_step(
    session_id: str,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Expert approves the current pending step and resumes the workflow."""
    try:
        session = await approve_step(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_to_dict(session)


@router.post("/workflow/{session_id}/reject")
async def reject_workflow_step(
    session_id: str,
    body: RejectRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Expert rejects a step and provides feedback for revision."""
    try:
        session = await reject_step(session_id, body.feedback)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_dict(session)


@router.post("/sk-plan")
async def sk_plan(
    body: SKPlanRequest,
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Semantic Kernel sequential planner: decomposes the goal into steps,
    retrieves relevant context for each step, and returns structured results.
    """
    try:
        planner = get_sk_planner()
        result  = await planner.execute_plan_async(body.goal)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.post("/sk-sharepoint-sync")
async def sk_sharepoint_sync(
    library: str = "Documents",
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Pull PDFs from a SharePoint document library and ingest them into the
    knowledge base. Skips files that are already present.
    """
    try:
        result = await sync_sharepoint_to_knowledge_base(library)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result
