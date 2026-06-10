"""
H5.1 LDAP/AD 认证提供者
使用 ldap3 库（运行时可选依赖）
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LDAPError(Exception):
    pass


class LDAPProvider:
    """
    LDAP/Active Directory 认证。
    配置示例：
      server, port, base_dn, bind_dn, bind_password,
      user_search_filter (default: (sAMAccountName={username}))
    """

    def __init__(self, config: dict):
        self.server      = config["server"]
        self.port        = int(config.get("port", 389))
        self.base_dn     = config["base_dn"]
        self.bind_dn     = config.get("bind_dn", "")
        self.bind_pw     = config.get("bind_password", "")
        self.use_ssl     = config.get("use_ssl", False)
        self.search_filter = config.get(
            "user_search_filter", "(sAMAccountName={username})"
        )
        self.attr_map = config.get("attr_map", {
            "email": "mail",
            "name": "displayName",
            "groups": "memberOf",
        })

    def _get_server(self):
        try:
            import ldap3
            return ldap3.Server(
                self.server, port=self.port,
                use_ssl=self.use_ssl, get_info=ldap3.ALL,
            )
        except ImportError:
            raise LDAPError("ldap3 未安装，请运行: pip install ldap3")

    async def authenticate(self, username: str, password: str) -> dict | None:
        """
        验证用户凭据，成功返回用户属性字典，失败返回 None。
        实际绑定是同步的；如需异步需在线程池中执行。
        """
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_authenticate, username, password
        )

    def _sync_authenticate(self, username: str, password: str) -> dict | None:
        try:
            import ldap3
            server = self._get_server()
            search_f = self.search_filter.format(username=username)

            # 用管理账号先搜索用户 DN
            conn = ldap3.Connection(server, self.bind_dn, self.bind_pw, auto_bind=True)
            conn.search(self.base_dn, search_f, attributes=list(self.attr_map.values()))

            if not conn.entries:
                return None

            user_dn = conn.entries[0].entry_dn

            # 用用户自己的密码绑定验证
            user_conn = ldap3.Connection(server, user_dn, password)
            if not user_conn.bind():
                return None

            entry = conn.entries[0]
            return {
                local: str(entry[remote].value) if entry[remote] else None
                for local, remote in self.attr_map.items()
            }
        except LDAPError:
            raise
        except Exception as e:
            logger.warning("LDAP authenticate error: %s", e)
            return None

    async def get_user_groups(self, username: str) -> list[str]:
        """获取用户所属 AD 组列表。"""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_get_groups, username
        )

    def _sync_get_groups(self, username: str) -> list[str]:
        try:
            import ldap3
            server = self._get_server()
            conn   = ldap3.Connection(server, self.bind_dn, self.bind_pw, auto_bind=True)
            search_f = self.search_filter.format(username=username)
            conn.search(self.base_dn, search_f, attributes=["memberOf"])
            if not conn.entries:
                return []
            member_of = conn.entries[0]["memberOf"].values or []
            return [str(g) for g in member_of]
        except Exception as e:
            logger.warning("LDAP get_user_groups error: %s", e)
            return []

    async def test_connection(self) -> bool:
        try:
            import ldap3
            server = self._get_server()
            conn = ldap3.Connection(server, self.bind_dn, self.bind_pw)
            return conn.bind()
        except Exception as e:
            logger.warning("LDAP test_connection failed: %s", e)
            return False
