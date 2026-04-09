"""
src/services/multimodal_writer.py
多模态知识图谱写入服务

将图片分析结果写入 Neo4j：
- Image 节点：存储图片元数据和 VLM 分析结果
- Section-[:HAS_IMAGE]->Image 关系
- Image-[:MENTIONS_TOOL]->Tool 节点
- 图片描述写入 Milvus 向量库和 ES
"""
import logging
import json
from pathlib import Path
from neo4j import Driver
from .es_store import get_es

logger = logging.getLogger(__name__)


def write_images_to_graph(
    driver:  Driver,
    doc_id:  str,
    images:  list[dict],
) -> None:
    """
    批量写入图片节点到 Neo4j
    images: [{"image_id", "page", "path", "caption", "analysis": {...}}]
    """
    with driver.session() as session:
        for img in images:
            analysis = img.get("analysis", {})

            drawing = img.get("drawing", {})
            # 写入 Image 节点（含图纸专项字段）
            session.run("""
                MERGE (i:Image {image_id: $image_id})
                SET i.doc_id             = $doc_id,
                    i.page               = $page,
                    i.path               = $path,
                    i.caption            = $caption,
                    i.description        = $description,
                    i.keywords           = $keywords,
                    i.dimensions         = $dimensions,
                    i.tools              = $tools,
                    i.is_drawing         = $is_drawing,
                    i.part_numbers       = $part_numbers,
                    i.annotations        = $annotations,
                    i.assembly_relations = $assembly_relations,
                    i.drawing_summary    = $drawing_summary
            """,
                image_id          = img["image_id"],
                doc_id            = doc_id,
                page              = img["page"],
                path              = img["path"],
                caption           = img.get("caption", ""),
                description       = analysis.get("description", ""),
                keywords          = json.dumps(analysis.get("keywords", []), ensure_ascii=False),
                dimensions        = json.dumps(analysis.get("dimensions", []), ensure_ascii=False),
                tools             = json.dumps(analysis.get("tools", []), ensure_ascii=False),
                is_drawing        = drawing.get("is_drawing", False),
                part_numbers      = json.dumps(drawing.get("part_numbers", []), ensure_ascii=False),
                annotations       = json.dumps(drawing.get("annotations", []), ensure_ascii=False),
                assembly_relations= json.dumps(drawing.get("assembly_relations", []), ensure_ascii=False),
                drawing_summary   = drawing.get("summary", ""),
            )

            # 关联到文档
            session.run("""
                MATCH (d:Document {name: $doc_id})
                MATCH (i:Image    {image_id: $image_id})
                MERGE (d)-[:HAS_IMAGE]->(i)
            """, doc_id=doc_id, image_id=img["image_id"])

            # 关联到对应页的章节（按页码匹配）
            session.run("""
                MATCH (s:Section)
                WHERE s.doc_id = $doc_id
                MATCH (i:Image {image_id: $image_id})
                WITH s, i
                ORDER BY s.section_number
                LIMIT 1
                MERGE (s)-[:HAS_IMAGE]->(i)
            """, doc_id=doc_id, image_id=img["image_id"])

        logger.info("写入 %d 张图片节点 doc_id=%s", len(images), doc_id)

    # 写入 ES（图片描述可搜索）
    _index_images_to_es(images, doc_id)

    # 写入 Milvus（图片描述向量化）
    _embed_images_to_milvus(images, doc_id)


def _index_images_to_es(images: list[dict], doc_id: str) -> None:
    """把图片描述写入 ES，支持跨图片搜索"""
    try:
        from elasticsearch.helpers import bulk
        es      = get_es()
        actions = []
        for img in images:
            analysis = img.get("analysis", {})
            desc     = analysis.get("description", img.get("caption", ""))
            if not desc:
                continue
            actions.append({
                "_index": "cps_images",
                "_id":    img["image_id"],
                "_source": {
                    "image_id":   img["image_id"],
                    "doc_id":     doc_id,
                    "page":       img["page"],
                    "caption":    img.get("caption", ""),
                    "description": desc,
                    "keywords":   analysis.get("keywords", []),
                    "tools":      analysis.get("tools", []),
                },
            })
        if actions:
            bulk(es, actions)
            logger.info("ES 写入 %d 张图片描述", len(actions))
    except Exception as e:
        logger.warning("图片写入 ES 失败: %s", e)


def _embed_images_to_milvus(images: list[dict], doc_id: str) -> None:
    """把图片描述向量化写入 Milvus"""
    try:
        from .embedder     import embed_texts
        from .milvus_store import upsert_sections

        texts = []
        milvus_data = []
        for img in images:
            analysis = img.get("analysis", {})
            desc     = analysis.get("description", img.get("caption", ""))
            if not desc:
                continue
            texts.append(desc)
            milvus_data.append({
                "chunk_id":  img["image_id"],
                "doc_id":    doc_id,
                "text":      desc,
                "embedding": None,  # 待填充
            })

        if not texts:
            return

        embeddings = embed_texts(texts)
        for i, item in enumerate(milvus_data):
            item["embedding"] = embeddings[i]

        upsert_sections(milvus_data)
        logger.info("Milvus 写入 %d 张图片向量", len(milvus_data))
    except Exception as e:
        logger.warning("图片写入 Milvus 失败: %s", e)