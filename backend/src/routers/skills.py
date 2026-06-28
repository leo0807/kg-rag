"""Skills API — expose agent skills as HTTP endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..skills.knowledge_skills import SKILL_DEFINITIONS, dispatch_skill

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCallRequest(BaseModel):
    name: str
    arguments: dict = {}


@router.get("/")
async def list_skills():
    """Return all available skill definitions."""
    return {"skills": SKILL_DEFINITIONS}


@router.post("/call")
async def call_skill(request: SkillCallRequest):
    """Execute a skill by name with provided arguments."""
    try:
        result = await dispatch_skill(request.name, request.arguments)
        return {"skill": request.name, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
