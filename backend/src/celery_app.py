"""
Celery 应用实例。

在 src/ 下以便 Dockerfile `COPY src/` 能覆盖到此文件。
Worker 启动命令（从 /app 目录执行）：
    celery -A src.celery_app worker --loglevel=info --concurrency=2
"""
import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "kg_rag",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "src.tasks.reprocess_tasks",
        "src.tasks.ingest_tasks",
        "src.tasks.graph_tasks",
        "src.tasks.ingestion_tasks",
        "src.tasks.eval_tasks",
        "src.tasks.quality_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # worker 故障时任务重回队列
    worker_prefetch_multiplier=1,  # 一次只预取一个任务，适合长任务
    result_expires=86400 * 7,      # 结果在 Redis 保留 7 天
    task_ignore_result=False,
)
