from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ...auth.deps import get_admin_user
from ...db.models import User
from ...prompts import registry

router = APIRouter(prefix="/api/admin/prompts", tags=["admin"])


class PromptRenderRequest(BaseModel):
    version: str | None = None
    ab_test: bool = False
    variables: dict[str, Any] = Field(default_factory=dict)


class PromptUpdateRequest(BaseModel):
    version: str | None = None
    active_version: str | None = None
    description: str | None = None
    model_preference: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    system: str | None = None
    user: str | None = None
    variables: list[str] | None = None
    weight: int | None = None


@router.get("")
async def list_prompts(_: User = Depends(get_admin_user)):
    registry.reload()
    return {"templates": registry.list_templates()}


@router.get("/{template_id}")
async def get_prompt(template_id: str, version: str | None = None, _: User = Depends(get_admin_user)):
    try:
        return registry.get(template_id, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{template_id}/render")
async def render_prompt(
    template_id: str,
    payload: PromptRenderRequest = Body(default_factory=PromptRenderRequest),
    _: User = Depends(get_admin_user),
):
    try:
        return registry.render(
            template_id,
            version=payload.version,
            ab_test=payload.ab_test,
            **payload.variables,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{template_id}")
async def update_prompt(
    template_id: str,
    payload: PromptUpdateRequest,
    _: User = Depends(get_admin_user),
):
    try:
        return registry.update_template(template_id, payload.model_dump(exclude_none=True), version=payload.version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
