from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import settings
from .logging import MaskingFilter


def setup_logging(level: str = "INFO") -> None:
    """统一日志配置：终端 + 文件，保留脱敏。"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(MaskingFilter())
    root.addHandler(stdout_handler)

    app_handler = RotatingFileHandler(
        log_dir / "backend.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setFormatter(formatter)
    app_handler.addFilter(MaskingFilter())
    root.addHandler(app_handler)

    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(MaskingFilter())
    root.addHandler(error_handler)

    for noisy in ("httpx", "httpcore", "urllib3", "neo4j", "pymilvus"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "日志已初始化 level=%s 文件=%s", level.upper(), log_dir.resolve()
    )
