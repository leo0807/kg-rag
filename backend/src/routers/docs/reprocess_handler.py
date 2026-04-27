"""批量重处理后台任务逻辑与状态持久化"""
import asyncio
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_BATCH_STATE_FILE = Path("batch_state.json")


def load_batch_state() -> dict:
    """启动时从文件恢复上次批量任务状态。"""
    try:
        if _BATCH_STATE_FILE.exists():
            state = json.loads(_BATCH_STATE_FILE.read_text(encoding="utf-8"))
            if state.get("status") == "running":
                state["status"] = "interrupted"
                state["message"] = '服务重启，任务被中断，可点击"续跑"继续'
            return state
    except Exception as e:
        logger.warning("批量状态文件读取失败: %s", e)
    return {"status": "idle"}


def save_batch_state(state: dict) -> None:
    try:
        _BATCH_STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, default=str), encoding="utf-8"
        )
    except Exception as e:
        logger.warning("批量状态文件写入失败: %s", e)


async def run_batch(batch: dict, doc_ids: list[str], pipelines: list[str]) -> None:
    """在 FastAPI 事件循环内后台运行批量重处理，逐文档顺序执行。"""
    from ...services.ingestion.reprocess_service import reprocess_document
    from ...core.database import get_driver

    driver = get_driver()
    total  = len(doc_ids)
    done   = 0
    errors: list[dict] = []
    completed_docs: list[str] = []

    try:
        for doc_id in doc_ids:
            if batch.get("cancel_requested"):
                break

            batch.update(current_doc=doc_id, message="准备处理...",
                         done=done, errors=errors, completed_docs=completed_docs)

            task_proxy: dict = {
                "doc_id": doc_id, "status": "pending", "pipelines": pipelines,
                "current": "", "message": "", "results": {}, "error": "",
                "snapshot_id": None, "cancel_requested": False,
                "started_at": None, "finished_at": None,
            }

            def _on_step(name: str, msg: str):
                batch.update(current_step=name, message=msg)

            try:
                await asyncio.to_thread(reprocess_document, doc_id, driver, pipelines, task_proxy, _on_step)
                if task_proxy.get("status") != "cancelled":
                    completed_docs.append(doc_id)
            except Exception as exc:
                logger.error("批量重处理文档 %s 失败: %s", doc_id, exc, exc_info=True)
                errors.append({"doc_id": doc_id, "error": str(exc)})

            done += 1
            batch.update(done=done, errors=errors, completed_docs=completed_docs)
            save_batch_state(batch)

        was_cancelled = bool(batch.get("cancel_requested"))
        batch.update(
            status="cancelled" if was_cancelled else "completed",
            done=done, current_doc="",
            message="已中止" if was_cancelled else "全部完成",
            errors=errors, completed_docs=completed_docs,
            finished_at=int(time.time()),
        )
        save_batch_state(batch)

    except Exception as exc:
        logger.error("批量重处理整体异常: %s", exc, exc_info=True)
        batch.update(status="failed", message=str(exc), finished_at=int(time.time()))
        save_batch_state(batch)
