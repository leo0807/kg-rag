"""
语义缓存服务 — 基于向量相似度避免重复检索和 LLM 推理

架构:
  Milvus(semantic_cache_v1) — 存储问题向量，余弦相似度查找
  Redis(scache:v:{id})      — 存储实际答案 + 元数据，带 TTL
  Redis(scache:d:{doc_id})  — doc_id → SET[cache_id]，用于按文档批量失效
  Redis(scache:cfg:*)       — 配置项（threshold / ttl / enabled）

工作流:
  查询 → 向量编码 → Milvus 最近邻 → 相似度 > threshold → Redis 命中 → 返回缓存答案
  未命中 → 走完整 RAG 管线 → 结果写入 Redis + Milvus
"""
import json
import logging
import time
import uuid

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "semantic_cache_v1"
DIM = 1024
DEFAULT_THRESHOLD = 0.95
DEFAULT_TTL       = 86400   # 24 小时


# ── Redis 辅助 ────────────────────────────────────────────────────────────────

def _r():
    from .cache import get_redis
    return get_redis()


# ── 配置 ──────────────────────────────────────────────────────────────────────

def get_config() -> dict:
    """读取语义缓存配置（存储于 Redis，可由管理后台动态修改）"""
    try:
        r = _r()
        return {
            "enabled":   r.get("scache:cfg:enabled")   != "0",
            "threshold": float(r.get("scache:cfg:threshold") or DEFAULT_THRESHOLD),
            "ttl":       int(r.get("scache:cfg:ttl")        or DEFAULT_TTL),
        }
    except Exception:
        return {"enabled": True, "threshold": DEFAULT_THRESHOLD, "ttl": DEFAULT_TTL}


def set_config(
    threshold: float | None = None,
    ttl:       int   | None = None,
    enabled:   bool  | None = None,
):
    r = _r()
    if threshold is not None: r.set("scache:cfg:threshold", threshold)
    if ttl       is not None: r.set("scache:cfg:ttl",       ttl)
    if enabled   is not None: r.set("scache:cfg:enabled",   "1" if enabled else "0")


# ── Milvus Collection ─────────────────────────────────────────────────────────

def _get_collection():
    from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
    if utility.has_collection(CACHE_COLLECTION):
        col = Collection(CACHE_COLLECTION)
        col.load()
        return col
    fields = [
        FieldSchema("cache_id",  DataType.VARCHAR,      max_length=36,   is_primary=True),
        FieldSchema("strategy",  DataType.VARCHAR,      max_length=32),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=DIM),
    ]
    col = Collection(CACHE_COLLECTION, CollectionSchema(fields, "语义缓存向量索引"))
    col.create_index("embedding",
        {"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 64}})
    col.load()
    logger.info("语义缓存 Milvus Collection 已创建: %s", CACHE_COLLECTION)
    return col


# ── 核心操作 ──────────────────────────────────────────────────────────────────

def lookup(embedding: list[float], strategy: str) -> dict | None:
    """
    查找语义相似历史问题的缓存。
    返回缓存数据 dict（含 similarity、cache_id）或 None。
    """
    cfg = get_config()
    if not cfg["enabled"]:
        return None
    try:
        col = _get_collection()
        results = col.search(
            data=[embedding], anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 8}},
            limit=1,
            expr=f'strategy == "{strategy}"' if strategy else None,
            output_fields=["cache_id", "strategy"],
        )
        if not results or not results[0]:
            return None
        hit = results[0][0]
        if float(hit.score) < cfg["threshold"]:
            return None
        cache_id = hit.entity.get("cache_id")
        raw = _r().get(f"scache:v:{cache_id}")
        if not raw:
            return None          # Redis TTL 已过期
        data = json.loads(raw)
        data["similarity"] = round(float(hit.score), 4)
        data["cache_id"]   = cache_id
        return data
    except Exception as e:
        logger.warning("语义缓存查找失败: %s", e)
        return None


def store(
    embedding:        list[float],
    strategy:         str,
    answer:           str,
    sources:          list[dict],
    question_preview: str       = "",
    doc_ids:          list[str] | None = None,
) -> str:
    """
    将查询结果写入语义缓存，返回 cache_id。
    """
    cfg = get_config()
    if not cfg["enabled"] or not answer.strip():
        return ""
    cache_id = str(uuid.uuid4())
    payload  = json.dumps({
        "answer":           answer,
        "sources":          sources,
        "question_preview": question_preview[:200],
        "doc_ids":          doc_ids or [],
        "strategy":         strategy,
        "created_at":       int(time.time()),
    }, ensure_ascii=False)
    try:
        r = _r()
        r.setex(f"scache:v:{cache_id}", cfg["ttl"], payload)
        for doc_id in (doc_ids or []):
            r.sadd(f"scache:d:{doc_id}", cache_id)
            r.expire(f"scache:d:{doc_id}", cfg["ttl"] + 3600)
        col = _get_collection()
        col.insert([[cache_id], [strategy], [embedding]])
        logger.info("语义缓存写入 cache_id=%s strategy=%s", cache_id[:8], strategy)
    except Exception as e:
        logger.warning("语义缓存写入失败: %s", e)
    return cache_id


def invalidate_by_doc(doc_id: str) -> int:
    """按 doc_id 批量失效缓存，返回失效条数"""
    try:
        r = _r()
        cache_ids = list(r.smembers(f"scache:d:{doc_id}") or [])
        if not cache_ids:
            return 0
        r.delete(*[f"scache:v:{cid}" for cid in cache_ids])
        r.delete(f"scache:d:{doc_id}")
        try:
            col = _get_collection()
            ids_expr = "[" + ", ".join(f'"{cid}"' for cid in cache_ids) + "]"
            col.delete(f"cache_id in {ids_expr}")
        except Exception as e:
            logger.warning("Milvus 缓存删除失败: %s", e)
        logger.info("语义缓存失效 doc_id=%s count=%d", doc_id, len(cache_ids))
        return len(cache_ids)
    except Exception as e:
        logger.warning("缓存失效失败 doc_id=%s: %s", doc_id, e)
        return 0


def get_stats() -> dict:
    """统计当前活跃缓存条目数"""
    try:
        r = _r()
        count = 0
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match="scache:v:*", count=500)
            count += len(keys)
            if cursor == 0:
                break
        return {"active_entries": count, "config": get_config()}
    except Exception as e:
        logger.warning("缓存统计失败: %s", e)
        return {"active_entries": 0, "config": get_config()}
