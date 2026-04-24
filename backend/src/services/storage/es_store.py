"""
src/services/es_store.py
Elasticsearch 全文检索服务

替代 Neo4j 全文索引，提供：
- 更好的中文分词
- 搜索结果高亮
- 聚合统计
- 横向扩展能力
"""
import logging
from functools import lru_cache
from elasticsearch import Elasticsearch
from ...core.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "cps_sections"

MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "ik_smart_analyzer": {
                    "type":      "custom",
                    "tokenizer": "ik_smart",
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "doc_id":   {"type": "keyword"},
            "number":   {"type": "keyword"},
            "title":    {"type": "text", "analyzer": "ik_smart_analyzer"},
            "content":  {"type": "text", "analyzer": "ik_smart_analyzer"},
        }
    }
}


@lru_cache(maxsize=1)
def get_es() -> Elasticsearch:
    es = Elasticsearch(settings.ES_URL)
    logger.info("Elasticsearch 连接成功: %s", settings.ES_URL)
    return es


def init_es_index() -> None:
    """创建索引，如果已存在则跳过"""
    es = get_es()
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=MAPPING)
        logger.info("ES 索引创建完成: %s", INDEX_NAME)
    else:
        logger.info("ES 索引已存在: %s", INDEX_NAME)


def index_sections(sections: list[dict]) -> None:
    """
    批量写入章节到 ES
    sections: [{"chunk_id": ..., "doc_id": ..., "number": ..., "title": ..., "content": ...}]
    """
    es = get_es()
    from elasticsearch.helpers import bulk

    actions = [
        {
            "_index": INDEX_NAME,
            "_id":    s["chunk_id"],
            "_source": {
                "chunk_id": s["chunk_id"],
                "doc_id":   s["doc_id"],
                "number":   s.get("number", ""),
                "title":    s.get("title", ""),
                "content":  s.get("content", ""),
            },
        }
        for s in sections
    ]
    bulk(es, actions)
    logger.info("ES 写入 %d 个章节", len(sections))


def search_sections_es(
    query:    str,
    top_k:    int  = 10,
    doc_id:   str  = "",
    highlight: bool = True,
) -> list[dict]:
    """
    ES 全文检索
    返回：[{"chunk_id": ..., "score": ..., "highlight": ...}]
    """
    es = get_es()

    must = [
        {
            "multi_match": {
                "query":  query,
                "fields": ["title^2", "content"],  # title 权重 2 倍
                "type":   "best_fields",
            }
        }
    ]

    if doc_id:
        must.append({"term": {"doc_id": doc_id}})

    body = {
        "query": {"bool": {"must": must}},
        "size":  top_k,
    }

    if highlight:
        body["highlight"] = {
            "fields": {
                "title":   {"number_of_fragments": 0},
                "content": {"fragment_size": 150, "number_of_fragments": 2},
            },
            "pre_tags":  ["<mark>"],
            "post_tags": ["</mark>"],
        }

    result = es.search(index=INDEX_NAME, body=body)
    hits   = result["hits"]["hits"]

    return [
        {
            "chunk_id":  hit["_source"]["chunk_id"],
            "doc_id":    hit["_source"]["doc_id"],
            "number":    hit["_source"]["number"],
            "title":     hit["_source"]["title"],
            "score":     hit["_score"],
            "highlight": hit.get("highlight", {}),
        }
        for hit in hits
    ]
