"""
Celery 批量重处理任务。

与 FastAPI 进程完全解耦：worker 自行创建 Neo4j driver，
不依赖 FastAPI 依赖注入（Depends），因此登录态过期不影响任务执行。
"""
import logging
import os
import time

from src.celery_app import celery_app
from src.tasks.driver_helpers import make_celery_driver

logger = logging.getLogger(__name__)

# Redis key 前缀：用于前端/API 发送取消信号
CANCEL_KEY_PREFIX = "reprocess_cancel_"


def _make_redis():
    import redis
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


@celery_app.task(bind=True, name="reprocess_batch")
def reprocess_batch_task(self, doc_ids: list[str], pipelines: list[str]):
    """
    对指定文档列表依次运行重处理管道。

    进度通过 Celery state="PROGRESS" 推送到 Redis result backend，
    可通过 AsyncResult(task_id).info 读取。

    取消：向 Redis 写入 key=reprocess_cancel_{task_id} 即可。
    """
    from src.services.ingestion.reprocess_service import reprocess_document

    driver = make_celery_driver()
    redis_client = _make_redis()
    cancel_key = f"{CANCEL_KEY_PREFIX}{self.request.id}"

    total = len(doc_ids)
    done = 0
    errors: list[dict] = []
    completed_docs: list[str] = []
    started_at = int(time.time())

    def _push(current_doc: str = "", current_step: str = "", message: str = ""):
        """将当前进度写入 Celery result backend（Redis）。"""
        self.update_state(
            state="PROGRESS",
            meta={
                "status":         "running",
                "total":          total,
                "done":           done,
                "current_doc":    current_doc,
                "current_step":   current_step,
                "message":        message,
                "pipelines":      pipelines,
                "errors":         errors,
                "completed_docs": completed_docs,
                "started_at":     started_at,
                "finished_at":    None,
            },
        )

    try:
        _push()

        for doc_id in doc_ids:
            # 检查取消信号（每次处理一个文档前）
            if redis_client.get(cancel_key):
                logger.info("取消信号收到，停止批量处理 (task=%s)", self.request.id)
                break

            _push(current_doc=doc_id, message="准备处理...")

            # 为 reprocess_document 准备独立的任务代理 dict（可传递取消信号）
            task_proxy: dict = {
                "doc_id":           doc_id,
                "status":           "pending",
                "pipelines":        pipelines,
                "current":          "",
                "message":          "",
                "results":          {},
                "error":            "",
                "snapshot_id":      None,
                "cancel_requested": False,
                "started_at":       None,
                "finished_at":      None,
            }

            def _on_step(name: str, msg: str):
                _push(current_doc=doc_id, current_step=name, message=msg)

            try:
                # 传入 on_step 回调，reprocess_document 内部会调用它来报告更细致的进度
                reprocess_document(doc_id, driver, pipelines, task_proxy, on_step=_on_step)
                if task_proxy.get("status") != "cancelled":
                    completed_docs.append(doc_id)
            except Exception as exc:
                logger.error("处理文档 %s 失败: %s", doc_id, exc, exc_info=True)
                errors.append({"doc_id": doc_id, "error": str(exc)})

            done += 1
            _push(current_doc=doc_id, message="处理完成")

        # 判断是否因取消信号而提前退出
        was_cancelled = bool(redis_client.get(cancel_key))
        redis_client.delete(cancel_key)

        final_status = "cancelled" if was_cancelled else "completed"
        return {
            "status":         final_status,
            "total":          total,
            "done":           done,
            "current_doc":    "",
            "message":        "完成" if final_status == "completed" else "已中止",
            "pipelines":      pipelines,
            "errors":         errors,
            "completed_docs": completed_docs,
            "started_at":     started_at,
            "finished_at":    int(time.time()),
        }

    finally:
        driver.close()
