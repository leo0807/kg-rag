"""Celery task 专用的 Neo4j driver 工厂。

不依赖 FastAPI lifespan，可在独立 worker 进程中安全使用。
"""
from __future__ import annotations

import os

from neo4j import GraphDatabase, Driver


def make_celery_driver() -> Driver:
    """为 Celery task 创建独立的 Neo4j driver。

    每个 task 调用一次；task 结束后由调用方负责 driver.close()。
    不复用 FastAPI 进程的全局 driver（后者依赖 lifespan 初始化）。
    """
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "aviation123"),
        ),
    )
