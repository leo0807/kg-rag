"""
H8.1 多渠道消息推送服务
Email / 钉钉 / 企业微信 / 飞书 / SMS
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MessagingError(Exception):
    pass


# ── Email ──────────────────────────────────────────────────────────────

class EmailSender:
    def __init__(self, host: str, port: int, username: str, password: str, use_tls: bool = True):
        self.host     = host
        self.port     = port
        self.username = username
        self.password = password
        self.use_tls  = use_tls

    async def send(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        attachments: list[dict] | None = None,
    ) -> bool:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_send, to if isinstance(to, list) else [to], subject, body, html
        )

    def _sync_send(self, to: list[str], subject: str, body: str, html: bool) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"]    = self.username
            msg["To"]      = ", ".join(to)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))

            with smtplib.SMTP(self.host, self.port) as s:
                if self.use_tls:
                    s.starttls()
                s.login(self.username, self.password)
                s.sendmail(self.username, to, msg.as_string())
            return True
        except Exception as e:
            logger.warning("email send failed: %s", e)
            return False


# ── 机器人 webhook（钉钉/企微/飞书）─────────────────────────────────────

async def _post_webhook(url: str, payload: dict, timeout: int = 10) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, json=payload)
            return r.status_code < 400
    except Exception as e:
        logger.warning("webhook post failed: %s", e)
        return False


async def send_dingtalk(webhook_url: str, title: str, text: str) -> bool:
    """钉钉机器人 markdown 消息。"""
    return await _post_webhook(webhook_url, {
        "msgtype": "markdown",
        "markdown": {"title": title, "text": text},
    })


async def send_wecom(webhook_url: str, content: str) -> bool:
    """企业微信机器人文本消息。"""
    return await _post_webhook(webhook_url, {
        "msgtype": "text",
        "text": {"content": content},
    })


async def send_feishu(webhook_url: str, title: str, content: str) -> bool:
    """飞书机器人 card 消息。"""
    return await _post_webhook(webhook_url, {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "div", "text": {"tag": "plain_text", "content": content}}],
        },
    })


# ── SMS（通用 HTTP 网关）─────────────────────────────────────────────────

async def send_sms(gateway_url: str, api_key: str, phone: str, message: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(gateway_url, json={
                "api_key": api_key, "to": phone, "message": message,
            })
            return r.status_code < 400
    except Exception as e:
        logger.warning("SMS send failed: %s", e)
        return False


# ── MessagingService 统一门面 ───────────────────────────────────────────

class MessagingService:
    """统一消息发送门面，根据渠道路由到具体实现。"""

    def __init__(self, config: dict):
        self._config = config
        email_cfg = config.get("email", {})
        self._email: EmailSender | None = (
            EmailSender(
                email_cfg["host"], int(email_cfg.get("port", 587)),
                email_cfg["username"], email_cfg["password"],
                email_cfg.get("use_tls", True),
            ) if email_cfg.get("host") else None
        )

    async def send(self, channel: str, recipient: str, subject: str, body: str) -> bool:
        """统一发送入口。channel: email/dingtalk/wecom/feishu/sms"""
        try:
            if channel == "email" and self._email:
                return await self._email.send(recipient, subject, body, html=True)
            if channel == "dingtalk":
                return await send_dingtalk(recipient, subject, body)
            if channel == "wecom":
                return await send_wecom(recipient, f"{subject}\n{body}")
            if channel == "feishu":
                return await send_feishu(recipient, subject, body)
            if channel == "sms":
                cfg = self._config.get("sms", {})
                return await send_sms(cfg.get("gateway_url", ""), cfg.get("api_key", ""), recipient, body)
        except Exception as e:
            logger.error("messaging.send(%s) error: %s", channel, e)
        return False

    def render_template(self, template: str, variables: dict) -> str:
        """简单变量替换 ${var}。"""
        try:
            return Template(template).safe_substitute(variables)
        except Exception:
            return template
