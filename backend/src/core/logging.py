"""
backend/src/core/logging.py
日志配置
"""
import logging
import sys
from .config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    ))

    logging.basicConfig(level=level, handlers=[handler], force=True)

    for noisy in ("httpx", "httpcore", "neo4j", "pymilvus"):
        logging.getLogger(noisy).setLevel(logging.WARNING)