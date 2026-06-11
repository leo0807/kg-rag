"""
I4.3: Field-level AES-256-GCM encryption for sensitive data at rest.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
    logger.warning("cryptography 库未安装，字段加密不可用。pip install cryptography")


class FieldEncryption:
    """
    AES-256-GCM field encryption.

    Key source priority:
      1. Explicit key passed to constructor.
      2. FIELD_ENCRYPTION_KEY env-var (base64 or hex, 32 bytes).
      3. Disabled (no-op passthrough) — plaintext is stored as-is.
    """

    _VERSION = b"\x01"   # one-byte version prefix for forward-compat

    def __init__(self, key: Optional[bytes] = None) -> None:
        self._key: Optional[bytes] = key or self._load_key()
        if self._key and len(self._key) != 32:
            raise ValueError("加密密钥必须是 32 字节 (AES-256)")

    def _load_key(self) -> Optional[bytes]:
        raw = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()
        if not raw:
            return None
        try:
            data = base64.b64decode(raw)
            return data if len(data) == 32 else None
        except Exception:
            pass
        try:
            data = bytes.fromhex(raw)
            return data if len(data) == 32 else None
        except Exception:
            return None

    @property
    def enabled(self) -> bool:
        return _HAS_CRYPTO and self._key is not None

    def encrypt(self, plaintext: str) -> str:
        """Return base64-encoded ciphertext. No-op if encryption is disabled."""
        if not self.enabled or not plaintext:
            return plaintext
        nonce = os.urandom(12)          # 96-bit nonce for GCM
        ct = AESGCM(self._key).encrypt(nonce, plaintext.encode(), None)
        payload = self._VERSION + nonce + ct
        return base64.b64encode(payload).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Return plaintext. Returns ciphertext unchanged if decryption fails."""
        if not self.enabled or not ciphertext:
            return ciphertext
        try:
            data = base64.b64decode(ciphertext)
            _ver, nonce, ct = data[0:1], data[1:13], data[13:]
            return AESGCM(self._key).decrypt(nonce, ct, None).decode()
        except Exception as e:
            logger.warning("字段解密失败: %s", e)
            return ciphertext

    def rotate(self, ciphertext: str, new_key: bytes) -> str:
        """Re-encrypt with a new key (for key rotation)."""
        plaintext = self.decrypt(ciphertext)
        old_key = self._key
        self._key = new_key
        result = self.encrypt(plaintext)
        self._key = old_key
        return result


# Module-level singleton (lazy-initialized from env)
_instance: Optional[FieldEncryption] = None


def get_field_encryption() -> FieldEncryption:
    global _instance
    if _instance is None:
        _instance = FieldEncryption()
    return _instance
