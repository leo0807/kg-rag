"""
MLflow model registry management endpoints.

GET  /api/admin/models                      — list all registered models
GET  /api/admin/models/{name}/versions      — version history for a model
PUT  /api/admin/models/{name}/activate      — promote version to Production
POST /api/admin/models/{name}/rollback      — roll back to previous Production
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...auth.deps import get_admin_user
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/models", tags=["admin"])

MLFLOW_URL = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


async def _mlflow_get(path: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{MLFLOW_URL}/api/2.0/mlflow/{path}", params=params)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


async def _mlflow_post(path: str, body: dict) -> Any:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{MLFLOW_URL}/api/2.0/mlflow/{path}", json=body)
    r.raise_for_status()
    return r.json()


class ActivateRequest(BaseModel):
    version: str
    alias:   str = "Production"


class RollbackRequest(BaseModel):
    alias: str = "Production"


@router.get("")
async def list_models(
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """List all registered models in the MLflow Model Registry."""
    try:
        data = await _mlflow_get("registered-models/list")
        models = data.get("registered_models", []) if data else []
        return {
            "count":  len(models),
            "models": [
                {
                    "name":           m["name"],
                    "creation_time":  m.get("creation_timestamp"),
                    "last_updated":   m.get("last_updated_timestamp"),
                    "latest_versions": [
                        {"version": v["version"], "stage": v.get("current_stage", "")}
                        for v in m.get("latest_versions", [])
                    ],
                }
                for m in models
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MLflow unreachable: {exc}")


@router.get("/{name}/versions")
async def model_versions(
    name: str,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """List all versions of a specific model."""
    try:
        data = await _mlflow_get(
            "model-versions/search",
            params={"filter": f"name='{name}'", "max_results": 50},
        )
        versions = data.get("model_versions", []) if data else []
        return {
            "name":     name,
            "count":    len(versions),
            "versions": [
                {
                    "version":       v["version"],
                    "stage":         v.get("current_stage", ""),
                    "run_id":        v.get("run_id", ""),
                    "description":   v.get("description", ""),
                    "creation_time": v.get("creation_timestamp"),
                }
                for v in sorted(versions, key=lambda x: -int(x.get("version", 0)))
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MLflow unreachable: {exc}")


@router.put("/{name}/activate")
async def activate_model_version(
    name: str,
    body: ActivateRequest,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """
    Promote a model version to Production (or any target alias/stage).
    The previous Production version is automatically archived.
    """
    try:
        result = await _mlflow_post("model-versions/transition-stage", {
            "name":    name,
            "version": body.version,
            "stage":   body.alias,
            "archive_existing_versions": True,
        })
        return {
            "ok":      True,
            "name":    name,
            "version": body.version,
            "stage":   body.alias,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{name}/rollback")
async def rollback_model(
    name: str,
    body: RollbackRequest,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """
    Roll back a model to the most recent Archived version.
    The current Production version becomes Archived.
    """
    try:
        data     = await _mlflow_get(
            "model-versions/search",
            params={"filter": f"name='{name}'", "max_results": 50},
        )
        versions = data.get("model_versions", []) if data else []

        archived = sorted(
            [v for v in versions if v.get("current_stage") == "Archived"],
            key=lambda x: -int(x.get("version", 0)),
        )
        if not archived:
            raise HTTPException(status_code=404, detail="No archived version to roll back to")

        prev = archived[0]
        await _mlflow_post("model-versions/transition-stage", {
            "name":    name,
            "version": prev["version"],
            "stage":   body.alias,
            "archive_existing_versions": True,
        })
        return {"ok": True, "rolled_back_to": prev["version"]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
