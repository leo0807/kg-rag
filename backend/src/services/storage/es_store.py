"""
src/services/storage/es_store.py
Elasticsearch 混合检索服务（BM25 + 向量 KNN + RRF）

支持：
- IK 中文分词（ik_max_word 索引 / ik_smart 检索）
- dense_vector 1024 维（bge-m3）
- ES 8.x 原生 RRF 混合检索
- 向量缺失时自动降级到纯全文检索
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk as es_bulk

from ...core.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "cps_sections"
EMBEDDING_DIMS = 1024

MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "ik_index": {
                    "type": "custom",
                    "tokenizer": "ik_max_word",
                },
                "ik_search": {
                    "type": "custom",
                    "tokenizer": "ik_smart",
                },
            }
        },
    },
    "mappings": {
        "properties": {
            "chunk_id":   {"type": "keyword"},
            "doc_id":     {"type": "keyword"},
            "number":     {"type": "keyword"},
            "title":      {"type": "text", "analyzer": "ik_index", "search_analyzer": "ik_search"},
            "content":    {"type": "text", "analyzer": "ik_index", "search_analyzer": "ik_search"},
            "level":      {"type": "integer"},
            "doc_title":  {"type": "text",    "analyzer": "ik_index", "search_analyzer": "ik_search"},
            "page_num":   {"type": "integer"},
            "created_at": {"type": "date"},
            "embedding": {
                "type": "dense_vector",
                "dims": EMBEDDING_DIMS,
                "index": True,
                "similarity": "cosine",
            },
        }
    },
}

# Fallback mapping when IK plugin is not available
MAPPING_STANDARD = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "chunk_id":   {"type": "keyword"},
            "doc_id":     {"type": "keyword"},
            "number":     {"type": "keyword"},
            "title":      {"type": "text"},
            "content":    {"type": "text"},
            "level":      {"type": "integer"},
            "doc_title":  {"type": "text"},
            "page_num":   {"type": "integer"},
            "created_at": {"type": "date"},
            "embedding": {
                "type": "dense_vector",
                "dims": EMBEDDING_DIMS,
                "index": True,
                "similarity": "cosine",
            },
        }
    },
}


@lru_cache(maxsize=1)
def get_es() -> Elasticsearch:
    es = Elasticsearch(settings.ES_URL, request_timeout=30)
    logger.info("Elasticsearch 连接: %s", settings.ES_URL)
    return es


def ensure_index() -> None:
    """创建索引（如已存在则跳过）。IK 不可用时自动降级到 standard 分词。"""
    es = get_es()
    if es.indices.exists(index=INDEX_NAME):
        logger.info("ES 索引已存在: %s", INDEX_NAME)
        return
    try:
        es.indices.create(index=INDEX_NAME, body=MAPPING)
        logger.info("ES 索引创建成功（IK 分词）: %s", INDEX_NAME)
    except Exception as exc:
        if "analyzer" in str(exc).lower() or "ik" in str(exc).lower():
            logger.warning("IK 分词器不可用，降级为 standard: %s", exc)
            es.indices.create(index=INDEX_NAME, body=MAPPING_STANDARD)
            logger.info("ES 索引创建成功（standard 分词）: %s", INDEX_NAME)
        else:
            raise


# ── 保持向后兼容的别名 ────────────────────────────────────────────────────────
def init_es_index() -> None:
    ensure_index()


# ── 写入 ──────────────────────────────────────────────────────────────────────

def index_section(section: dict, embedding: list[float] | None = None) -> None:
    """写入单个章节。embedding 可选；缺失时该文档仅支持全文检索。"""
    es = get_es()
    doc = {
        "chunk_id":   section["chunk_id"],
        "doc_id":     section["doc_id"],
        "number":     section.get("number", ""),
        "title":      section.get("title", ""),
        "content":    section.get("content", ""),
        "level":      section.get("level", 0),
        "doc_title":  section.get("doc_title", ""),
        "page_num":   section.get("page_num", 0),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if embedding:
        doc["embedding"] = embedding
    es.index(index=INDEX_NAME, id=section["chunk_id"], document=doc)


def index_sections(sections: list[dict], embeddings: list[list[float]] | None = None) -> None:
    """
    批量写入章节（向后兼容原 index_sections(sections) 签名）。
    embeddings: 与 sections 等长的向量列表，可选。
    """
    es = get_es()
    emb_map: dict[str, list[float]] = {}
    if embeddings and len(embeddings) == len(sections):
        emb_map = {s["chunk_id"]: e for s, e in zip(sections, embeddings)}

    actions = []
    for s in sections:
        doc: dict = {
            "chunk_id":   s["chunk_id"],
            "doc_id":     s["doc_id"],
            "number":     s.get("number", ""),
            "title":      s.get("title", ""),
            "content":    s.get("content", ""),
            "level":      s.get("level", 0),
            "doc_title":  s.get("doc_title", ""),
            "page_num":   s.get("page_num", 0),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        emb = emb_map.get(s["chunk_id"])
        if emb:
            doc["embedding"] = emb
        actions.append({
            "_index":  INDEX_NAME,
            "_id":     s["chunk_id"],
            "_source": doc,
        })

    if actions:
        es_bulk(es, actions)
        logger.info("ES 批量写入 %d 条", len(actions))


def delete_section(chunk_id: str) -> None:
    try:
        get_es().delete(index=INDEX_NAME, id=chunk_id)
    except NotFoundError:
        pass
    except Exception as exc:
        logger.warning("ES delete 失败 chunk_id=%s: %s", chunk_id, exc)


def delete_doc(doc_id: str) -> None:
    """删除某文档的所有章节。"""
    try:
        get_es().delete_by_query(
            index=INDEX_NAME,
            body={"query": {"term": {"doc_id": doc_id}}},
            refresh=True,
        )
    except Exception as exc:
        logger.warning("ES delete_by_query 失败 doc_id=%s: %s", doc_id, exc)


# ── 检索 ──────────────────────────────────────────────────────────────────────

def hybrid_search(
    query: str,
    query_embedding: list[float] | None = None,
    top_k: int = 10,
    doc_ids: list[str] | None = None,
) -> list[dict]:
    """
    混合检索：BM25 + KNN 向量，通过 ES 8.x 原生 RRF 融合排名。
    query_embedding 为 None 时自动降级为纯 BM25 全文检索。
    """
    es = get_es()

    # BM25 全文查询
    bm25: dict = {
        "multi_match": {
            "query": query,
            "fields": ["title^2", "content"],
            "type": "best_fields",
        }
    }
    if doc_ids:
        bm25 = {
            "bool": {
                "must": bm25,
                "filter": [{"terms": {"doc_id": doc_ids}}],
            }
        }

    body: dict = {
        "query": bm25,
        "size": top_k,
        "_source": {"excludes": ["embedding"]},
    }

    if query_embedding:
        knn: dict = {
            "field": "embedding",
            "query_vector": query_embedding,
            "k": top_k * 2,
            "num_candidates": top_k * 10,
        }
        if doc_ids:
            knn["filter"] = {"terms": {"doc_id": doc_ids}}

        body["knn"] = knn
        body["rank"] = {
            "rrf": {
                "window_size": top_k * 4,
                "rank_constant": 60,
            }
        }

    response = es.search(index=INDEX_NAME, body=body)
    results = []
    for hit in response["hits"]["hits"]:
        src = dict(hit["_source"])
        src["es_score"] = hit["_score"] or 0.0
        results.append(src)
    return results


def search_sections_es(
    query: str,
    top_k: int = 10,
    doc_id: str = "",
    highlight: bool = True,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    """
    向后兼容的全文检索接口（原调用方不传 embedding 时走纯 BM25）。
    新调用方可传 query_embedding 触发混合检索。
    """
    doc_ids = [doc_id] if doc_id else None
    hits = hybrid_search(query, query_embedding=query_embedding, top_k=top_k, doc_ids=doc_ids)

    results = []
    for h in hits:
        row = {
            "chunk_id": h.get("chunk_id", ""),
            "doc_id":   h.get("doc_id", ""),
            "number":   h.get("number", ""),
            "title":    h.get("title", ""),
            "content":  h.get("content", ""),
            "score":    h["es_score"],
            "highlight": {},
        }
        results.append(row)
    return results
