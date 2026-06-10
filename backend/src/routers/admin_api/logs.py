"""Admin API — 日志查询（文件读取 + 过滤）"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from ...auth.deps import get_admin_user
from ...db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/logs", tags=["admin-logs"])

LOG_DIR = Path("logs")
_LEVEL_RE = re.compile(r'\|\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\|', re.IGNORECASE)


def _level_of(line: str) -> str:
    m = _LEVEL_RE.search(line)
    return m.group(1).upper() if m else "INFO"


def _level_rank(level: str) -> int:
    return {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}.get(level.upper(), 1)


def _tail_lines(path: Path, n: int = 2000) -> list[str]:
    """Read last n lines efficiently without loading the whole file."""
    if not path.exists():
        return []
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        buf_size = min(size, n * 200)
        f.seek(max(0, size - buf_size))
        raw = f.read()
    lines = raw.decode("utf-8", errors="replace").splitlines()
    return lines[-n:]


@router.get("")
async def query_logs(
    level: str = Query("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    search: Optional[str] = Query(None, max_length=200),
    trace_id: Optional[str] = Query(None, max_length=100),
    file: str = Query("backend", pattern="^(backend|errors)$"),
    lines: int = Query(200, ge=10, le=2000),
    _admin: User = Depends(get_admin_user),
):
    """查询日志（从文件末尾读取，支持级别、关键词、trace_id 过滤）。"""
    log_file = LOG_DIR / f"{file}.log"
    raw = _tail_lines(log_file, 5000)

    min_rank = _level_rank(level)
    result = []
    for line in raw:
        if not line.strip():
            continue
        line_level = _level_of(line)
        if _level_rank(line_level) < min_rank:
            continue
        if search and search.lower() not in line.lower():
            continue
        if trace_id and trace_id not in line:
            continue
        result.append(line)

    return {
        "total": len(result),
        "lines": result[-lines:],
        "file": file,
        "log_dir": str(LOG_DIR.resolve()),
    }


@router.get("/files")
async def list_log_files(_admin: User = Depends(get_admin_user)):
    """列出所有日志文件及大小。"""
    if not LOG_DIR.exists():
        return []
    files = []
    for p in sorted(LOG_DIR.glob("*.log*")):
        files.append({
            "name": p.name,
            "size_bytes": p.stat().st_size,
            "size": _fmt_size(p.stat().st_size),
        })
    return files


@router.get("/download/{filename}")
async def download_log(
    filename: str,
    _admin: User = Depends(get_admin_user),
):
    """下载日志文件（纯文本）。"""
    # 防止路径穿越
    safe = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    path = LOG_DIR / safe
    if not path.exists() or not path.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, "日志文件不存在")
    return PlainTextResponse(
        content=path.read_text(errors="replace"),
        headers={"Content-Disposition": f"attachment; filename={safe}"},
    )


def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b //= 1024
    return f"{b} TB"
