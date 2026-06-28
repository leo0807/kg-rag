"""
A2A (Agent-to-Agent) Protocol endpoints.
Implements Google's A2A spec v0.2 for inter-agent task delegation.

Exposed endpoints:
  GET  /.well-known/agent.json   — Agent Card
  POST /api/a2a/tasks/send       — Receive delegated task
  POST /api/a2a/tasks/sendSubscribe — SSE streaming task
  GET  /api/a2a/tasks/{task_id}  — Task status poll
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(tags=["a2a"])

# In-memory task store (replace with Redis/DB for production)
_tasks: dict[str, dict] = {}


# ─── Agent Card ───────────────────────────────────────────────────────────────

AGENT_CARD = {
    "name": "CPS Knowledge Base Agent",
    "description": (
        "Aerospace manufacturing process knowledge agent. "
        "Provides knowledge graph-augmented Q&A over aviation procedure specifications."
    ),
    "url": "http://localhost:8000",
    "version": "1.0.0",
    "capabilities": {
        "streaming": True,
        "stateTransitionHistory": True,
    },
    "skills": [
        {
            "id": "query_knowledge_base",
            "name": "Query Knowledge Base",
            "description": "Answer questions about aerospace process specifications",
            "inputModes": ["text"],
            "outputModes": ["text"],
            "examples": [
                "What is the torque specification for hydraulic fitting installation?",
                "Which sections reference GJB 241?",
            ],
        },
        {
            "id": "search_entities",
            "name": "Search Entities",
            "description": "Find tools, materials, processes in the knowledge graph",
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
        {
            "id": "get_graph_path",
            "name": "Knowledge Path",
            "description": "Find relationship path between two knowledge nodes",
            "inputModes": ["text"],
            "outputModes": ["text"],
        },
    ],
    "authentication": {
        "schemes": ["Bearer", "ApiKey"],
    },
}


@router.get("/.well-known/agent.json", include_in_schema=False)
async def agent_card():
    return JSONResponse(AGENT_CARD)


# ─── Task models ──────────────────────────────────────────────────────────────

class A2AMessage(BaseModel):
    role: str = "user"
    parts: list[dict] = Field(default_factory=list)


class A2ATaskRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: A2AMessage
    skill_id: str | None = None
    metadata: dict = Field(default_factory=dict)


# ─── Task execution ───────────────────────────────────────────────────────────

async def _execute_task(task_id: str, request: A2ATaskRequest) -> None:
    """Execute a delegated task asynchronously."""
    _tasks[task_id]["status"] = "working"
    _tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()

    try:
        text_parts = [p["text"] for p in request.message.parts if p.get("type") == "text"]
        question = " ".join(text_parts)

        if not question:
            raise ValueError("No text content in task message")

        # Import here to avoid circular dependency
        import httpx
        async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60) as c:
            r = await c.post(
                "/api/query",
                json={"question": question, "strategy": "parallel", "top_k": 5},
            )
            data = r.json()

        answer = data.get("answer", "No answer returned")
        sources = data.get("sources", [])

        _tasks[task_id].update({
            "status": "completed",
            "result": {
                "role": "agent",
                "parts": [
                    {"type": "text", "text": answer},
                    {
                        "type": "data",
                        "data": {"sources": [
                            {"title": s.get("title"), "doc_id": s.get("doc_id")}
                            for s in sources[:5]
                        ]},
                    },
                ],
            },
            "updated_at": datetime.utcnow().isoformat(),
        })
    except Exception as exc:
        log.exception("A2A task %s failed", task_id)
        _tasks[task_id].update({
            "status": "failed",
            "error": str(exc),
            "updated_at": datetime.utcnow().isoformat(),
        })


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/api/a2a/tasks/send")
async def send_task(request: A2ATaskRequest):
    """Receive a delegated task and return task ID. Executes asynchronously."""
    task_id = request.id
    _tasks[task_id] = {
        "id": task_id,
        "status": "submitted",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "skill_id": request.skill_id,
    }
    asyncio.create_task(_execute_task(task_id, request))
    return {"id": task_id, "status": "submitted"}


@router.post("/api/a2a/tasks/sendSubscribe")
async def send_task_subscribe(request: A2ATaskRequest):
    """SSE streaming task execution (A2A streaming mode)."""
    task_id = request.id
    _tasks[task_id] = {
        "id": task_id,
        "status": "working",
        "created_at": datetime.utcnow().isoformat(),
    }

    async def event_stream() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'id': task_id, 'status': 'working'})}\n\n"
        await _execute_task(task_id, request)
        task = _tasks.get(task_id, {})
        yield f"data: {json.dumps(task)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/a2a/tasks/{task_id}")
async def get_task(task_id: str):
    """Poll task status."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
