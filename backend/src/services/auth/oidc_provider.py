"""
H5.1 OIDC/OAuth2 单点登录提供者
支持标准 OpenID Connect discovery，兼容 Azure AD / Google / Keycloak 等
"""
from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class OIDCError(Exception):
    pass


class OIDCProvider:
    """
    标准 OIDC 接入器。
    配置示例（来自 tenants.settings['sso']['oidc']）：
      client_id, client_secret, discovery_url, redirect_uri,
      scope (默认 openid email profile), user_mapping
    """

    def __init__(self, config: dict):
        self.client_id     = config["client_id"]
        self.client_secret = config["client_secret"]   # 不存明文，运行时解密后传入
        self.redirect_uri  = config["redirect_uri"]
        self.scope         = config.get("scope", "openid email profile")
        self.user_mapping  = config.get("user_mapping", {
            "email": "email", "name": "name", "sub": "sub"
        })
        self._discovery_url = config["discovery_url"]
        self._meta: dict | None = None

    async def _metadata(self) -> dict:
        if self._meta is None:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(self._discovery_url)
                r.raise_for_status()
                self._meta = r.json()
        return self._meta

    async def get_authorization_url(self, state: str) -> str:
        """生成授权跳转 URL，前端重定向到此地址。"""
        meta = await self._metadata()
        params = {
            "response_type": "code",
            "client_id":     self.client_id,
            "redirect_uri":  self.redirect_uri,
            "scope":         self.scope,
            "state":         state,
            "nonce":         secrets.token_hex(16),
        }
        return f"{meta['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> dict:
        """Authorization Code → Access/ID Token。"""
        meta = await self._metadata()
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                meta["token_endpoint"],
                data={
                    "grant_type":    "authorization_code",
                    "code":          code,
                    "redirect_uri":  self.redirect_uri,
                    "client_id":     self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code != 200:
                raise OIDCError(f"token exchange failed: {r.text[:200]}")
            return r.json()

    async def get_user_info(self, access_token: str) -> dict:
        """用 access_token 获取用户信息并映射字段。"""
        meta = await self._metadata()
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                meta["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            raw = r.json()

        mapped = {}
        for local_key, remote_key in self.user_mapping.items():
            mapped[local_key] = raw.get(remote_key)
        mapped["_raw"] = raw
        return mapped

    async def refresh_token(self, refresh_token: str) -> dict:
        meta = await self._metadata()
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                meta["token_endpoint"],
                data={
                    "grant_type":    "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id":     self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            return r.json()


def build_oidc_from_tenant(settings: dict) -> OIDCProvider | None:
    """从租户 settings 字典构建 OIDCProvider，不可用时返回 None。"""
    sso = settings.get("sso", {})
    if sso.get("type") != "oidc":
        return None
    try:
        return OIDCProvider(sso)
    except KeyError as e:
        logger.warning("OIDC config incomplete: missing %s", e)
        return None
