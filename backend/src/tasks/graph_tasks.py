"""F122-B: 图谱链路预测 Celery task"""
import logging

from ..celery_app import celery_app
from .driver_helpers import make_celery_driver

logger = logging.getLogger(__name__)

_PREDICTION_RUNNING_KEY = "link_prediction_running"


@celery_app.task(bind=True, name="run_graph_prediction")
def run_graph_prediction(self, top_k: int = 50) -> dict:
    """触发链路预测并将结果写入 Redis 缓存。"""
    import redis
    import os

    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    r.set(_PREDICTION_RUNNING_KEY, "1", ex=3600)

    driver = make_celery_driver()
    try:
        from ..services.graph.link_prediction import run_and_cache_predictions
        self.update_state(state="PROGRESS", meta={"step": "running"})
        run_and_cache_predictions(driver, top_k)
        logger.info("链路预测完成 top_k=%d", top_k)
        return {"status": "done", "top_k": top_k}
    finally:
        r.delete(_PREDICTION_RUNNING_KEY)
        driver.close()
