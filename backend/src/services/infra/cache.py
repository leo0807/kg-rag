"""
src/services/cache.py
Redis 缓存服务
"""
import json
import hashlib
import logging
from functools import lru_cache
import redis
from ...core.config import settings

logger = logging.getLogger(__name__)

QUERY_CACHE_VERSION = "v37"


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def make_cache_key(question: str, strategy: str, top_k: int) -> str:
    """生成缓存 key，用 MD5 避免特殊字符问题"""
    raw = f"{QUERY_CACHE_VERSION}:{question}:{strategy}:{top_k}"
    return f"query:{hashlib.md5(raw.encode()).hexdigest()}"


def get_cached_result(question: str, strategy: str, top_k: int) -> dict | None:
    """获取缓存结果，不存在返回 None"""
    try:
        r   = get_redis()
        key = make_cache_key(question, strategy, top_k)
        val = r.get(key)
        if val:
            logger.info("缓存命中 key=%s", key[:16])
            return json.loads(val)
    except Exception as e:
        logger.warning("Redis 读取失败: %s", e)
    return None


def set_cached_result(
    question: str,
    strategy: str,
    top_k:    int,
    result:   dict,
) -> None:
    """写入缓存"""
    try:
        r   = get_redis()
        key = make_cache_key(question, strategy, top_k)
        r.setex(key, settings.QUERY_CACHE_TTL, json.dumps(result, ensure_ascii=False))
        logger.info("缓存写入 key=%s ttl=%ds", key[:16], settings.QUERY_CACHE_TTL)
    except Exception as e:
        logger.warning("Redis 写入失败: %s", e)
