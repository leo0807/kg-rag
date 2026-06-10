from __future__ import annotations

import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import settings
from .logging import MaskingFilter


class JsonFormatter(logging.Formatter):
    """结构化 JSON 日志格式器（容器环境 / 日志聚合用）。"""

    def format(self, record: logging.LogRecord) -> str:
        doc: dict = {
            "ts":      int(time.time() * 1000),
            "level":   record.levelname,
            "service": "backend",
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)
        # 附加 extra 字段（trace_id、user_id 等由中间件注入）
        for key in ("trace_id", "user_id", "path", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                doc[key] = val
        return json.dumps(doc, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """统一日志配置：终端（text/json）+ 文件（rotation）。"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    use_json = os.getenv("LOG_FORMAT", "text").lower() == "json"

    if use_json:
        text_formatter = JsonFormatter()
    else:
        fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
        text_formatter = logging.Formatter(fmt, datefmt="%H:%M:%S")

    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(text_formatter)
    stdout_handler.addFilter(MaskingFilter())
    root.addHandler(stdout_handler)

    app_handler = RotatingFileHandler(
        log_dir / "backend.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setFormatter(file_formatter)
    app_handler.addFilter(MaskingFilter())
    root.addHandler(app_handler)

    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(file_formatter)
    error_handler.addFilter(MaskingFilter())
    root.addHandler(error_handler)

    for noisy in ("httpx", "httpcore", "urllib3", "neo4j", "pymilvus"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "日志已初始化 level=%s format=%s 文件=%s",
        level.upper(), "json" if use_json else "text", log_dir.resolve(),
    )
