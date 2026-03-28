"""
src/core/logging.py
结构化日志配置
"""
import logging
import sys
import json
from datetime import datetime
from .config import settings


class JSONFormatter(logging.Formatter):
    """输出 JSON 格式的日志，方便 ELK / Loki 等日志系统解析"""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """开发模式下的可读格式"""
    def format(self, record: logging.LogRecord) -> str:
        return (
            f"{datetime.now().strftime('%H:%M:%S')}  "
            f"{record.levelname:<8}  "
            f"{record.name}  "
            f"{record.getMessage()}"
        )


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 开发模式用可读格式，生产模式用 JSON
    formatter = HumanFormatter() if settings.DEBUG else JSONFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=[handler], force=True)

    # 屏蔽噪音日志
    for noisy in ("httpx", "httpcore", "neo4j", "pymilvus", "passlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)