"""
F1.2: Audit middleware — automatically records sensitive HTTP operations.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..services.audit.audit_models import EventType, write_audit

logger = logging.getLogger(__name__)

# Paths that always need auditing regardless of method
_SENSITIVE_GET_PATTERNS = re.compile(
    r"/(export|download|backup|report|csv|xlsx|docx)", re.IGNORECASE
)

# Paths to skip entirely (health, metrics, static assets, SSE streams)
_SKIP_PATTERNS = re.compile(
    r"^/api/health|^/api/ws|^/uploads/|^/(docs|redoc|openapi\.json)|"
    r"^/api/query/stream|^/favicon",
    re.IGNORECASE,
)

# Path → resource_type mapping
_RESOURCE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/api/documents/"), "document"),
    (re.compile(r"/api/admin/eval/"), "eval"),
    (re.compile(r"/api/admin/users?/"), "user"),
    (re.compile(r"/api/sessions/"), "session"),
    (re.compile(r"/api/auth/"), "auth"),
    (re.compile(r"/api/admin/"), "admin"),
    (re.compile(r"/api/"), "api"),
]

# Auth endpoints get specific event types
_AUTH_TYPE_MAP = {
    "/api/auth/login": EventType.LOGIN,
    "/api/auth/logout": EventType.LOGOUT,
    "/api/auth/password": EventType.PASSWORD_CHANGE,
}


def _should_audit(method: str, path: str) -> bool:
    if _SKIP_PATTERNS.search(path):
        return False
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return True
    if method == "GET" and _SENSITIVE_GET_PATTERNS.search(path):
        return True
    return False


def _classify(method: str, path: str) -> tuple[str, str]:
    """Returns (event_type, action)."""
    for auth_path, etype in _AUTH_TYPE_MAP.items():
        if path.startswith(auth_path):
            return etype, "auth"
    action = {"POST": "create", "PUT": "update", "PATCH": "update",
               "DELETE": "delete", "GET": "read"}.get(method, "unknown")
    for pattern, rtype in _RESOURCE_MAP:
        if pattern.search(path):
            return f"{rtype}.{action}", action
    return f"api.{action}", action


def _extract_resource_id(path: str) -> str | None:
    m = re.search(r"/([a-f0-9\-]{8,}|[A-Z0-9]{4,})", path)
    return m.group(1) if m else None


async def _extract_user(request: Request) -> dict:
    """Extract user info from request state or token (best-effort)."""
    user_id = user_name = user_role = None
    try:
        if hasattr(request.state, "user") and request.state.user:
            u = request.state.user
            user_id = str(getattr(u, "id", ""))
            user_name = getattr(u, "username", None)
            user_role = "admin" if getattr(u, "is_admin", False) else "user"
        else:
            # Try decode JWT without verification just for logging
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                import base64, json as _json
                token = auth.split(" ")[1]
                parts = token.split(".")
                if len(parts) == 3:
                    pad = parts[1] + "=" * (4 - len(parts[1]) % 4)
                    payload = _json.loads(base64.urlsafe_b64decode(pad))
                    user_id = payload.get("sub")
    except Exception:
        pass
    return {"user_id": user_id, "user_name": user_name, "user_role": user_role}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path = request.url.path

        if not _should_audit(method, path):
            return await call_next(request)

        response = await call_next(request)
        success = response.status_code < 400

        # Fire audit write asynchronously — does not block response
        asyncio.create_task(self._log(request, method, path, response.status_code, success))
        return response

    async def _log(self, request: Request, method: str, path: str,
                   status_code: int, success: bool) -> None:
        user_info = await _extract_user(request)
        event_type, action = _classify(method, path)
        await write_audit(
            event_type=event_type,
            action=action,
            user_id=user_info["user_id"],
            user_name=user_info["user_name"],
            user_role=user_info["user_role"],
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:200],
            resource_type=event_type.split(".")[0],
            resource_id=_extract_resource_id(path),
            resource_name=path,
            success=success,
            error_message=None if success else f"HTTP {status_code}",
            trace_id=getattr(request.state, "trace_id", None),
            request_path=path[:400],
            request_method=method,
        )
