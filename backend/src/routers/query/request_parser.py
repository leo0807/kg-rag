from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import HTTPException, Request, UploadFile

from ...services.images.query_image_context import build_query_image_context
from ...services.security.upload_validator import validate_upload
from .models import QueryRequest

IMAGE_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
})
IMAGE_MAX_BYTES = 10 * 1024 * 1024


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_json_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _parse_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"无效的整数值: {value!r}")


def _parse_float(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"无效的浮点值: {value!r}")


def _data_uri_from_bytes(content: bytes, media_type: str) -> str:
    return f"data:{media_type};base64,{base64.b64encode(content).decode('utf-8')}"


async def _image_to_data_uri(file: UploadFile) -> str:
    content = await validate_upload(
        file,
        allowed_types=IMAGE_TYPES,
        max_bytes=IMAGE_MAX_BYTES,
    )
    media_type = file.content_type or "image/png"
    return _data_uri_from_bytes(content, media_type)


async def parse_query_request(request: Request) -> QueryRequest:
    content_type = (request.headers.get("content-type") or "").lower()
    if content_type.startswith("multipart/"):
        form = await request.form()
        files: list[UploadFile] = []
        for key in ("images", "image"):
            for item in form.getlist(key):
                if hasattr(item, "filename") and hasattr(item, "content_type"):
                    files.append(item)
        images = [await _image_to_data_uri(file) for file in files]
        image_context = (
            await build_query_image_context(
                images,
                caption=str(form.get("question") or "").strip(),
            )
            if images
            else ""
        )
        payload = {
            "question": str(form.get("question") or "").strip(),
            "strategy": str(form.get("strategy") or "parallel").strip() or "parallel",
            "top_k": _parse_int(form.get("top_k"), 5),
            "history": _parse_json_list(form.get("history")),
            "images": images,
            "image_context": image_context,
            "doc_hints": _parse_json_list(form.get("doc_hints")),
            "use_hyde": _parse_bool(form.get("use_hyde")),
            "hyde_alpha": _parse_float(form.get("hyde_alpha"), 0.5),
            "skip_clarification": _parse_bool(form.get("skip_clarification")),
        }
        return QueryRequest.model_validate(payload)

    body = await request.json()
    return QueryRequest.model_validate(body)
