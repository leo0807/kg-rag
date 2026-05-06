"""
src/core/logging.py
结构化日志配置（含脱敏过滤）
"""
import logging
import sys
import json
import re
from datetime import datetime
from .config import settings

SENSITIVE_PATTERNS = [
    (re.compile(r'\b\d{6}\b'),                                      "******"),          # 6位工号
    (re.compile(r'\b1[3-9]\d{9}\b'),                                "***-****-****"),   # 手机号
    (re.compile(r'\b\d{3,4}-\d{7,8}\b'),                           "***-*******"),     # 座机
    (re.compile(r'[\w.+-]+@[\w.-]+\.\w+'),                          "***@***.***"),     # 邮箱
    (re.compile(r'\b\d{17}[\dXx]\b'),                               "***...**"),        # 身份证
    (re.compile(r'(编制|审核|批准|拟制|校核)[：:\s]*[一-鿿]{2,4}'),   r'\1：***'),       # 姓名
]

def mask_message(msg: str) -> str:
    """对消息内容进行脱敏处理"""
    if not isinstance(msg, str):
        return msg
    for pattern, replacement in SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg

class MaskingFilter(logging.Filter):
    """日志脱敏过滤器：在日志输出前修改 record.msg"""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_message(record.msg)
        elif hasattr(record, "message"): # 某些 handler 已经 getMessage()
            record.message = mask_message(record.message)
        
        # 处理 args 中的敏感词
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(mask_message(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        return True

class JSONFormatter(logging.Formatter):
    """输出 JSON 格式的日志，方便 ELK / Loki 等日志系统解析"""

    def format(self, record: logging.LogRecord) -> str:
        # 确保在 format 之前已经脱敏（如果 Filter 没生效的话作为双保险）
        msg = mask_message(record.getMessage())
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level":     record.levelname,
            "logger":    record.name,
            "message":   msg,
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """开发模式下的可读格式"""
    def format(self, record: logging.LogRecord) -> str:
        msg = mask_message(record.getMessage())
        return (
            f"{datetime.now().strftime('%H:%M:%S')}  "
            f"{record.levelname:<8}  "
            f"{record.name}  "
            f"{msg}"
        )


def setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 开发模式用可读格式，生产模式用 JSON
    formatter = HumanFormatter() if settings.DEBUG else JSONFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # 添加脱敏过滤器
    handler.addFilter(MaskingFilter())

    logging.basicConfig(level=level, handlers=[handler], force=True)

    # 屏蔽噪音日志
    for noisy in ("httpx", "httpcore", "neo4j", "pymilvus", "passlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)