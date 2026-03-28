"""
src/services/milvus_store.py
Milvus 向量存储服务
"""
import logging
from functools import lru_cache
from pymilvus import (
    connections, Collection, CollectionSchema,
    FieldSchema, DataType, utility
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "cps_sections"
DIM             = 1024  # bge-m3 输出维度


def connect_milvus(host: str = "localhost", port: str = "19530") -> None:
    connections.connect("default", host=host, port=port)
    logger.info("Milvus 连接成功 %s:%s", host, port)


def get_or_create_collection() -> Collection:
    """获取或创建 Collection，保证幂等"""
    if utility.has_collection(COLLECTION_NAME):
        col = Collection(COLLECTION_NAME)
        col.load()
        return col

    fields = [
        FieldSchema("id",       DataType.VARCHAR, max_length=128, is_primary=True),
        FieldSchema("doc_id",   DataType.VARCHAR, max_length=64),
        FieldSchema("chunk_id", DataType.VARCHAR, max_length=128),
        FieldSchema("text",     DataType.VARCHAR, max_length=4096),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=DIM),
    ]
    schema = CollectionSchema(fields, description="CPS 章节向量库")
    col    = Collection(COLLECTION_NAME, schema)

    # 创建 IVF_FLAT 索引
    col.create_index(
        "embedding",
        {
            "index_type": "IVF_FLAT",
            "metric_type": "IP",        # 内积，配合归一化向量等价于余弦相似度
            "params": {"nlist": 128},
        }
    )
    col.load()
    logger.info("Milvus Collection 创建完成: %s", COLLECTION_NAME)
    return col


def upsert_sections(sections: list[dict]) -> None:
    """
    批量写入章节向量
    sections: [{"chunk_id": ..., "doc_id": ..., "text": ..., "embedding": [...]}]
    """
    col = get_or_create_collection()

    ids        = [s["chunk_id"] for s in sections]
    doc_ids    = [s["doc_id"]   for s in sections]
    chunk_ids  = [s["chunk_id"] for s in sections]
    texts      = [s["text"][:4000] for s in sections]
    embeddings = [s["embedding"]   for s in sections]

    col.upsert([ids, doc_ids, chunk_ids, texts, embeddings])
    logger.info("写入 Milvus %d 条向量", len(sections))


def search_sections(
    query_vec: list[float],
    top_k:     int = 10,
    doc_id:    str = "",
) -> list[dict]:
    """向量检索，返回最相关的章节"""
    col    = get_or_create_collection()
    expr   = f'doc_id == "{doc_id}"' if doc_id else ""

    results = col.search(
        data         = [query_vec],
        anns_field   = "embedding",
        param        = {"metric_type": "IP", "params": {"nprobe": 16}},
        limit        = top_k,
        expr         = expr or None,
        output_fields= ["chunk_id", "doc_id", "text"],
    )

    hits = []
    for hit in results[0]:
        hits.append({
            "chunk_id": hit.entity.get("chunk_id"),
            "doc_id":   hit.entity.get("doc_id"),
            "text":     hit.entity.get("text"),
            "score":    float(hit.score),
        })
    return hits