"""
GNN 管理 API

端点:
  GET  /api/gnn/status   — 查询嵌入加载状态与训练元数据
  POST /api/gnn/train    — 触发后台 GraphSAGE 训练任务
  POST /api/gnn/refresh  — 训练完成后热更新嵌入（无需重启服务）

权限: 需要已登录用户（管理员操作）
"""
import asyncio
import logging
import sys
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.gnn_service import get_gnn_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gnn", tags=["GNN"])

# ── 训练任务状态（进程级全局变量）────────────────────────────
_training: dict = {"running": False, "progress": "", "error": ""}


# ────────────────────────────────────────────────────────────
# 端点
# ────────────────────────────────────────────────────────────

@router.get("/status")
async def gnn_status():
    """返回 GNN 嵌入服务状态 + 上次训练的元数据"""
    svc = get_gnn_service()
    return {
        "service":  svc.get_status(),
        "training": _training,
    }


class TrainRequest(BaseModel):
    epochs:      int   = 100
    lr:          float = 1e-3
    batch_size:  int   = 256
    dropout:     float = 0.2
    temperature: float = 0.07
    patience:    int   = 15
    device:      str   = "cpu"


@router.post("/train")
async def trigger_train(req: TrainRequest = TrainRequest()):
    """
    后台启动 GraphSAGE 训练。
    训练期间可轮询 GET /api/gnn/status 查看进度。
    训练完成后嵌入自动热加载，无需重启服务。
    """
    if _training["running"]:
        raise HTTPException(status_code=409, detail="训练已在进行中，请等待完成")

    async def _run():
        global _training
        _training = {"running": True, "progress": "启动训练进程...", "error": ""}
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m", "backend.scripts.train_gnn",
                "--epochs",      str(req.epochs),
                "--lr",          str(req.lr),
                "--batch_size",  str(req.batch_size),
                "--dropout",     str(req.dropout),
                "--temperature", str(req.temperature),
                "--patience",    str(req.patience),
                "--device",      req.device,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            _training["progress"] = f"训练中 (epochs={req.epochs}, device={req.device})"
            stdout, _ = await proc.communicate()
            output = stdout.decode(errors="replace") if stdout else ""

            if proc.returncode == 0:
                _training["progress"] = "训练完成，正在热加载嵌入..."
                get_gnn_service().reload()
                _training["progress"] = "完成"
                logger.info("GNN 训练并热加载完成")
            else:
                _training["error"] = output[-2000:]   # 保留最后 2k 字符的错误日志
                logger.error("GNN 训练失败 (code=%d)", proc.returncode)
        except Exception as e:
            _training["error"] = str(e)
            logger.exception("GNN 训练异常")
        finally:
            _training["running"] = False

    asyncio.create_task(_run())
    return {"message": f"GraphSAGE 训练已启动 (epochs={req.epochs}, device={req.device})"}


@router.post("/refresh")
async def refresh_embeddings():
    """从磁盘热加载最新的 GNN 嵌入（适用于手动运行训练脚本后）"""
    svc = get_gnn_service()
    svc.reload()
    return svc.get_status()
