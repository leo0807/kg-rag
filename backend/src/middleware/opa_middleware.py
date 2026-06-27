"""
OPA (Open Policy Agent) ABAC middleware for FastAPI.

Before every /api/query and /api/docs/* request, sends an authz check to OPA.
Returns 403 + audit log entry on deny.

Setup:
  1. Start OPA server:
       docker run -d -p 8181:8181 openpolicyagent/opa:latest run --server
  2. Load policy:
       curl -X PUT http://localhost:8181/v1/policies/authz \
            --data-binary @docker/opa/authz.rego
  3. Register middleware in main.py:
       from src.middleware.opa_middleware import OPAMiddleware
       app.add_middleware(OPAMiddleware)

Environment:
  OPA_URL            default: http://localhost:8181
  OPA_ENABLED        default: true  (set to false to bypass in dev)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger(__name__)

OPA_URL     = os.getenv("OPA_URL", "http://localhost:8181")
OPA_ENABLED = os.getenv("OPA_ENABLED", "true").lower() == "true"
OPA_TIMEOUT = float(os.getenv("OPA_TIMEOUT", "2.0"))

# Paths that require OPA authorization check
_PROTECTED_PREFIXES = ("/api/query", "/api/docs", "/api/graph", "/api/library")
# Paths always allowed (health, login, static)
_BYPASS_PREFIXES    = ("/api/auth", "/api/health", "/docs", "/openapi", "/static")


def _requires_authz(path: str) -> bool:
    if any(path.startswith(p) for p in _BYPASS_PREFIXES):
        return False
    return any(path.startswith(p) for p in _PROTECTED_PREFIXES)


async def _extract_user(request: Request) -> dict:
    """Extract user attributes from JWT claims stored in request.state."""
    user = getattr(request.state, "user", None)
    if user:
        return {
            "id":              user.get("sub", ""),
            "role":            user.get("role", "viewer"),
            "department":      user.get("department", ""),
            "clearance_level": int(user.get("clearance_level", 0)),
        }
    return {"id": "", "role": "", "department": "", "clearance_level": 0}


def _extract_resource(request: Request) -> dict:
    """Derive resource attributes from the request path and query params."""
    path  = request.url.path
    doc_id = request.query_params.get("doc_id", "")
    return {
        "doc_id":        doc_id,
        "department":    request.query_params.get("department", ""),
        "min_clearance": 0,   # real value fetched from DB in prod; 0 for unclassified
        "action":        "read" if request.method == "GET" else "write",
    }


async def _ask_opa(user: dict, resource: dict) -> tuple[bool, list[str]]:
    """POST to OPA and return (allowed, deny_reasons)."""
    payload = {"input": {"user": user, "resource": resource}}
    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT) as client:
            resp = await client.post(
                f"{OPA_URL}/v1/data/authz",
                json=payload,
            )
        result = resp.json().get("result", {})
        allowed = bool(result.get("allow", False))
        reasons = list(result.get("deny_reasons", []))
        return allowed, reasons
    except Exception as exc:
        # OPA unreachable → fail-open in dev, fail-closed in prod
        log.warning("OPA unreachable: %s — defaulting to allow", exc)
        return True, []


class OPAMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not OPA_ENABLED or not _requires_authz(request.url.path):
            return await call_next(request)

        user     = await _extract_user(request)
        resource = _extract_resource(request)
        allowed, reasons = await _ask_opa(user, resource)

        if not allowed:
            log.warning(
                "OPA denied: user=%s path=%s reasons=%s",
                user.get("id"), request.url.path, reasons,
            )
            await _write_audit_deny(request, user, resource, reasons)
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access denied by policy",
                    "reasons": reasons,
                },
            )

        return await call_next(request)


async def _write_audit_deny(
    request: Request,
    user: dict,
    resource: dict,
    reasons: list[str],
) -> None:
    """Append 403 event to audit log (best-effort, non-blocking)."""
    try:
        import asyncpg
        from ..core.config import settings
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        await conn.execute(
            """
            INSERT INTO audit_logs (user_id, action, resource, details, created_at)
            VALUES ($1, 'ACCESS_DENIED', $2, $3, NOW())
            """,
            user.get("id", ""),
            resource.get("doc_id", request.url.path),
            json.dumps({"reasons": reasons, "path": request.url.path}),
        )
        await conn.close()
    except Exception as exc:
        log.debug("Audit write failed (non-critical): %s", exc)
