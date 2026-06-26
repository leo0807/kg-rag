"""
SSE backpressure / rate limiter: throttles streamed text to a configurable
chars-per-second rate to avoid overwhelming slow clients.
"""
from __future__ import annotations

import asyncio
import math
from typing import AsyncIterator

_CHUNK_SIZE = 20  # characters per yielded chunk


class SSERateLimiter:
    """Yields text chunks at a controlled chars-per-second rate."""

    def __init__(self, chars_per_second: int = 200) -> None:
        self.chars_per_second = chars_per_second

    async def throttle(self, text: str) -> AsyncIterator[str]:
        if not text:
            return

        # Unlimited mode
        if self.chars_per_second <= 0:
            yield text
            return

        delay_per_chunk = _CHUNK_SIZE / self.chars_per_second
        total = len(text)
        offset = 0

        while offset < total:
            chunk = text[offset: offset + _CHUNK_SIZE]
            offset += _CHUNK_SIZE
            yield chunk
            if offset < total:
                await asyncio.sleep(delay_per_chunk)


def get_sse_rate_limiter() -> SSERateLimiter:
    """Factory that reads SSE_CHARS_PER_SECOND from settings (0 = unlimited)."""
    try:
        from ...core.config import settings
        cps = getattr(settings, "SSE_CHARS_PER_SECOND", 0)
    except Exception:
        cps = 0
    return SSERateLimiter(chars_per_second=cps)
