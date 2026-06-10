"""Admin API — 备份管理（列表 / 触发 / 删除）"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

from ...auth.deps import get_admin_user
from ...db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/backups", tags=["admin-backups"])

# 备份目录（相对于工作目录；容器内为 /app/backups）
BACKUP_ROOT = Path("backups")


def _read_manifest(backup_dir: Path) -> dict:
    manifest = backup_dir / "manifest.json"
    if manifest.exists():
        try:
            return json.loads(manifest.read_text())
        except Exception:
            pass
    return {"timestamp": None, "total_size": "?", "components": []}


def _list_backups() -> list[dict]:
    if not BACKUP_ROOT.exists():
        return []
    entries = []
    for d in sorted(BACKUP_ROOT.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        meta = _read_manifest(d)
        entries.append({
            "id": d.name,
            "path": str(d),
            "timestamp": meta.get("timestamp"),
            "size": meta.get("total_size", "?"),
            "git_rev": meta.get("git_rev"),
            "components": meta.get("components", []),
        })
    return entries


async def _run_backup_script() -> tuple[bool, str]:
    proc = await asyncio.create_subprocess_exec(
        "bash", "scripts/backup.sh",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode(errors="replace") if stdout else ""
    return proc.returncode == 0, output


@router.get("")
async def list_backups(_admin: User = Depends(get_admin_user)):
    """列出所有备份（按时间倒序）。"""
    return _list_backups()


@router.post("")
async def trigger_backup(
    background_tasks: BackgroundTasks,
    _admin: User = Depends(get_admin_user),
):
    """触发一次全量备份（异步执行）。"""
    async def _do():
        ok, output = await _run_backup_script()
        if ok:
            logger.info("管理员触发备份完成")
        else:
            logger.error("管理员触发备份失败:\n%s", output)

    background_tasks.add_task(_do)
    return {"message": "备份已启动（后台执行）"}


@router.get("/{backup_id}")
async def get_backup(backup_id: str, _admin: User = Depends(get_admin_user)):
    """获取单个备份详情。"""
    path = BACKUP_ROOT / backup_id
    if not path.is_dir():
        raise HTTPException(404, "备份不存在")
    meta = _read_manifest(path)
    files = [f.name for f in path.iterdir() if not f.is_dir()]
    return {**meta, "id": backup_id, "files": files}


@router.delete("/{backup_id}")
async def delete_backup(backup_id: str, _admin: User = Depends(get_admin_user)):
    """删除指定备份目录。"""
    # 防止路径穿越
    path = (BACKUP_ROOT / backup_id).resolve()
    if not str(path).startswith(str(BACKUP_ROOT.resolve())):
        raise HTTPException(400, "非法路径")
    if not path.is_dir():
        raise HTTPException(404, "备份不存在")
    shutil.rmtree(path)
    logger.info("管理员删除备份: %s", backup_id)
    return {"ok": True}
