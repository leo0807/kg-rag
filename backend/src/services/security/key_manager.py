"""
I5.1: Unified key management supporting file, Vault, K8s, and cloud KMS backends.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _default_key_path() -> Path:
    """Resolve key store path: env var → project-local backend/keys/."""
    env_path = os.environ.get("KEY_STORE_PATH")
    if env_path:
        return Path(env_path)
    # Safe default: sits inside the repo, no root privileges needed
    return Path(__file__).resolve().parents[3] / "keys" / "keystore.json"


@dataclass
class KeyEntry:
    name: str
    version: int
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── Backend interfaces ────────────────────────────────────────────────────────

class _KeyStore(ABC):
    @abstractmethod
    async def get(self, name: str) -> Optional[str]: ...

    @abstractmethod
    async def set(self, name: str, value: str) -> None: ...

    @abstractmethod
    async def list_keys(self) -> List[str]: ...


class FileKeyStore(_KeyStore):
    """Stores keys in a JSON file.  Degrades gracefully when the directory
    is not writable (read-only mode — keys survive in memory only)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or _default_key_path()
        self._store: Dict[str, Any] = {}
        self._writable = False

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._writable = True
        except (PermissionError, OSError) as e:
            logger.warning(
                "密钥目录不可写 (%s)，KeyManager 降级为只读/内存模式。"
                "可设置环境变量 KEY_STORE_PATH 指定可写路径。",
                e,
            )

        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._store = json.loads(self._path.read_text())
            except Exception as e:
                logger.warning("密钥文件读取失败: %s", e)
                self._store = {}

    def _save(self) -> None:
        if not self._writable:
            return
        try:
            self._path.write_text(json.dumps(self._store, indent=2))
            self._path.chmod(0o600)
        except (PermissionError, OSError) as e:
            logger.warning("密钥文件写入失败: %s", e)

    async def get(self, name: str) -> Optional[str]:
        entry = self._store.get(name)
        return entry.get("value") if isinstance(entry, dict) else None

    async def set(self, name: str, value: str) -> None:
        existing = self._store.get(name, {})
        prev_version = existing.get("version", 0) if isinstance(existing, dict) else 0
        self._store[name] = {
            "value": value,
            "version": prev_version + 1,
            "updated_at": time.time(),
        }
        self._save()

    async def list_keys(self) -> List[str]:
        return list(self._store.keys())


class VaultKeyStore(_KeyStore):
    """HashiCorp Vault KV v2 backend."""

    def __init__(self) -> None:
        self._addr = os.getenv("VAULT_ADDR", "http://vault:8200")
        self._token = os.getenv("VAULT_TOKEN", "")
        self._mount = os.getenv("VAULT_MOUNT", "secret")

    async def get(self, name: str) -> Optional[str]:
        try:
            import httpx
            async with httpx.AsyncClient() as c:
                r = await c.get(
                    f"{self._addr}/v1/{self._mount}/data/{name}",
                    headers={"X-Vault-Token": self._token},
                    timeout=5.0,
                )
                if r.status_code == 200:
                    return r.json()["data"]["data"].get("value")
        except Exception as e:
            logger.warning("Vault get(%s) failed: %s", name, e)
        return None

    async def set(self, name: str, value: str) -> None:
        try:
            import httpx
            async with httpx.AsyncClient() as c:
                await c.post(
                    f"{self._addr}/v1/{self._mount}/data/{name}",
                    headers={"X-Vault-Token": self._token},
                    json={"data": {"value": value}},
                    timeout=5.0,
                )
        except Exception as e:
            logger.warning("Vault set(%s) failed: %s", name, e)

    async def list_keys(self) -> List[str]:
        return []


class EnvKeyStore(_KeyStore):
    """Read-only: reads keys from environment variables (for cloud deployments)."""

    async def get(self, name: str) -> Optional[str]:
        return os.getenv(name.upper().replace("-", "_"))

    async def set(self, name: str, value: str) -> None:
        raise NotImplementedError("EnvKeyStore is read-only")

    async def list_keys(self) -> List[str]:
        return []


# ── Key audit log ─────────────────────────────────────────────────────────────

class _AuditLog:
    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []

    def record(self, action: str, key_name: str, actor: str = "system") -> None:
        self._entries.append({
            "ts": time.time(),
            "action": action,
            "key": key_name,
            "actor": actor,
        })
        logger.info("[KEY_AUDIT] %s key=%s actor=%s", action, key_name, actor)

    def recent(self, key_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        entries = self._entries if key_name is None else [
            e for e in self._entries if e["key"] == key_name
        ]
        return entries[-limit:]


# ── Manager ───────────────────────────────────────────────────────────────────

class KeyManager:
    """Unified key management with audit trail and rotation support."""

    _BACKENDS = {
        "file":  FileKeyStore,
        "vault": VaultKeyStore,
        "env":   EnvKeyStore,
    }

    def __init__(self) -> None:
        backend_name = os.getenv("KEY_STORE_BACKEND", "file")
        cls = self._BACKENDS.get(backend_name, FileKeyStore)
        self._store: _KeyStore = cls()
        self._audit = _AuditLog()

    async def get_key(self, name: str, actor: str = "system") -> Optional[str]:
        value = await self._store.get(name)
        self._audit.record("GET", name, actor)
        return value

    async def set_key(self, name: str, value: str, actor: str = "system") -> None:
        await self._store.set(name, value)
        self._audit.record("SET", name, actor)

    async def rotate_key(self, name: str, new_value: str, actor: str = "system") -> None:
        old = await self._store.get(name)
        await self._store.set(f"{name}__prev", old or "")
        await self._store.set(name, new_value)
        self._audit.record("ROTATE", name, actor)
        logger.info("密钥已轮换: %s", name)

    async def list_keys(self) -> List[str]:
        return await self._store.list_keys()

    def audit_log(self, key_name: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._audit.recent(key_name)

    async def generate_random_key(self, name: str, length: int = 32) -> str:
        value = base64.b64encode(os.urandom(length)).decode()
        await self.set_key(name, value, actor="auto-generate")
        return value


# ── Lazy singleton ────────────────────────────────────────────────────────────

_key_manager: Optional[KeyManager] = None


def get_key_manager() -> KeyManager:
    """Return the shared KeyManager instance, creating it on first call."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager
