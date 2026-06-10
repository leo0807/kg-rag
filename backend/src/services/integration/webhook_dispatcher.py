"""
H6.2 Webhook 调度器
带签名、重试、投递记录
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    "answer.created", "feedback.submitted", "spec.generated",
    "evaluation.completed", "document.uploaded", "user.created",
    "quota.exceeded", "alert.triggered",
}

_MAX_ATTEMPTS  = 3
_RETRY_DELAYS  = [60, 300, 3600]   # 1min / 5min / 1h


class WebhookDispatcher:
    """从数据库加载 Webhook 配置并异步投递事件。"""

    def __init__(self, db_session_factory):
        self._factory = db_session_factory

    async def dispatch(self, event_type: str, payload: dict, tenant_id: str | None = None) -> None:
        """触发事件：异步投递，不阻塞调用方。"""
        if event_type not in EVENT_TYPES:
            logger.warning("unknown webhook event type: %s", event_type)
            return
        asyncio.create_task(self._fan_out(event_type, payload, tenant_id))

    async def _fan_out(self, event_type: str, payload: dict, tenant_id: str | None) -> None:
        from sqlalchemy import select
        from ...db.integration_models import Webhook, WebhookDelivery

        async with self._factory() as db:
            stmt = select(Webhook).where(Webhook.is_active == True)
            if tenant_id:
                stmt = stmt.where(Webhook.tenant_id == tenant_id)
            hooks = (await db.execute(stmt)).scalars().all()

        for wh in hooks:
            subscribed: list = wh.events or []
            if event_type not in subscribed and "*" not in subscribed:
                continue
            delivery_id = str(uuid.uuid4())
            asyncio.create_task(
                self._deliver(wh, event_type, payload, delivery_id, attempt=1)
            )

    async def _deliver(
        self,
        wh: Any,
        event_type: str,
        payload: dict,
        delivery_id: str,
        attempt: int,
    ) -> None:
        from sqlalchemy import select
        from ...db.integration_models import Webhook, WebhookDelivery

        body    = json.dumps(payload, ensure_ascii=False, default=str)
        sig     = _sign(body, wh.secret or "")
        headers = {
            "Content-Type":    "application/json",
            "X-KG-Event":      event_type,
            "X-KG-Signature":  f"sha256={sig}",
            "X-KG-Delivery-Id": delivery_id,
        }

        status, resp_body, error = "failed", "", ""
        resp_status = 0
        try:
            async with httpx.AsyncClient(timeout=wh.timeout_seconds) as c:
                r = await c.post(wh.url, content=body, headers=headers)
                resp_status = r.status_code
                resp_body   = r.text[:1000]
                status      = "success" if r.status_code < 400 else "failed"
        except Exception as e:
            error = str(e)[:500]

        async with self._factory() as db:
            delivery = WebhookDelivery(
                id=delivery_id, webhook_id=wh.id,
                event_type=event_type, payload=payload,
                status=status, response_status=resp_status,
                response_body=resp_body, attempt_count=attempt,
                completed_at=datetime.utcnow() if status == "success" else None,
            )
            db.add(delivery)

            hook = (await db.execute(select(Webhook).where(Webhook.id == wh.id))).scalar_one_or_none()
            if hook:
                hook.last_triggered_at = datetime.utcnow()
                if status == "success":
                    hook.success_count += 1
                else:
                    hook.failure_count += 1
            await db.commit()

        if status == "failed" and attempt <= _MAX_ATTEMPTS:
            delay = _RETRY_DELAYS[attempt - 1]
            logger.info("webhook %s retry %d in %ds", wh.id, attempt, delay)
            await asyncio.sleep(delay)
            await self._deliver(wh, event_type, payload, delivery_id, attempt + 1)


def _sign(body: str, secret: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


# 全局单例（由 main.py 初始化）
_dispatcher: WebhookDispatcher | None = None


def init_dispatcher(db_session_factory) -> None:
    global _dispatcher
    _dispatcher = WebhookDispatcher(db_session_factory)


def get_dispatcher() -> WebhookDispatcher | None:
    return _dispatcher
