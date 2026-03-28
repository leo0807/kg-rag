"""
backend/src/core/observability.py
Langfuse LLMOps 可观测性
"""
import base64
import logging

import requests

from .config import settings

logger = logging.getLogger(__name__)


def send_trace(
    name:     str,
    input:    str,
    output:   str,
    metadata: dict,
) -> None:
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return

    try:
        credentials = base64.b64encode(
            f"{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}".encode()
        ).decode()

        res = requests.post(
            f"{settings.LANGFUSE_HOST}/api/public/traces",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type":  "application/json",
            },
            json={
                "name":     name,
                "input":    input,
                "output":   output,
                "metadata": metadata,
            },
            timeout=5,
        )
        logger.info("Langfuse trace 已记录 id=%s", res.json().get("id"))
    except Exception as e:
        logger.warning("Langfuse 追踪失败: %s", e)