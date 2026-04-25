"""Backfill service facade preserving existing imports."""

from __future__ import annotations

from .backfill_helpers import (
    K_CURRENT,
    K_DONE,
    K_PAUSE,
    K_STARTED_AT,
    K_STATUS,
    K_STOP,
    K_TOTAL,
    _ALL_KEYS,
    _count_all_docs,
    _delete_existing_images_for_doc,
    _extract_images_for_doc,
    _find_pdf,
    _get_pending_docs,
    _redis,
    extract_images_for_doc,
)
from .backfill_runtime import (
    get_backfill_status,
    pause_backfill,
    resume_backfill,
    start_backfill,
    stop_backfill,
    try_resume_on_startup,
)

__all__ = [
    "K_CURRENT",
    "K_DONE",
    "K_PAUSE",
    "K_STARTED_AT",
    "K_STATUS",
    "K_STOP",
    "K_TOTAL",
    "_ALL_KEYS",
    "_count_all_docs",
    "_delete_existing_images_for_doc",
    "_extract_images_for_doc",
    "_find_pdf",
    "_get_pending_docs",
    "_redis",
    "extract_images_for_doc",
    "get_backfill_status",
    "pause_backfill",
    "resume_backfill",
    "start_backfill",
    "stop_backfill",
    "try_resume_on_startup",
]
