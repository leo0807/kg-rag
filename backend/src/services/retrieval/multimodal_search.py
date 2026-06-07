"""
src/services/retrieval/multimodal_search.py
图文混合检索：文字章节检索 + 图片 caption 检索 + 融合。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_IMAGE_CAPTION_SEARCH_LIMIT = 6


async def _caption_search(driver, question: str, doc_ids: list[str]) -> list[dict]:
    """用问题文本在 Neo4j Image 节点的 caption/description/keywords 中检索相关图片。"""
    # 取前3个词作检索词（避免太长）
    terms = [t.strip() for t in question.replace("？", " ").replace("？", " ").split() if len(t.strip()) >= 2][:3]
    if not terms:
        return []

    def _run() -> list[dict]:
        with driver.session() as session:
            cypher = """
                MATCH (i:Image)
                WHERE (
                    any(t IN $terms WHERE toLower(coalesce(i.caption, '')) CONTAINS toLower(t))
                    OR any(t IN $terms WHERE toLower(coalesce(i.description, '')) CONTAINS toLower(t))
                )
                AND ($doc_ids = [] OR i.doc_id IN $doc_ids)
                RETURN
                    i.image_id  AS image_id,
                    i.doc_id    AS doc_id,
                    coalesce(i.page_num, i.page, 0) AS page_num,
                    i.caption   AS caption,
                    i.description AS description,
                    i.minio_path  AS minio_path
                ORDER BY page_num
                LIMIT $limit
            """
            rows = session.run(cypher, terms=terms, doc_ids=doc_ids, limit=_IMAGE_CAPTION_SEARCH_LIMIT)
            result = []
            for row in rows:
                d = dict(row)
                d["url"] = f"/api/images/{d['image_id']}" if d.get("minio_path") else None
                result.append(d)
            return result

    try:
        return await asyncio.to_thread(_run)
    except Exception as e:
        logger.warning("caption 图片检索失败: %s", e)
        return []


async def _attach_section_images(driver, sections: list[dict]) -> list[dict]:
    """为每个 section 关联其 HAS_IMAGE 图片。"""
    chunk_ids = [s.get("chunk_id") for s in sections if s.get("chunk_id")]
    if not chunk_ids:
        return sections

    def _run() -> dict[str, list[dict]]:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (sec:Section)-[:HAS_IMAGE]->(i:Image)
                WHERE sec.chunk_id IN $chunk_ids
                RETURN
                    sec.chunk_id AS chunk_id,
                    i.image_id   AS image_id,
                    i.doc_id     AS doc_id,
                    coalesce(i.page_num, i.page, 0) AS page_num,
                    i.caption    AS caption,
                    i.minio_path AS minio_path
                LIMIT 30
                """,
                chunk_ids=chunk_ids,
            )
            mapping: dict[str, list[dict]] = {}
            for row in rows:
                cid = row["chunk_id"]
                img = {
                    "image_id": row["image_id"],
                    "doc_id":   row["doc_id"],
                    "page_num": row["page_num"],
                    "caption":  row["caption"],
                    "url": f"/api/images/{row['image_id']}" if row.get("minio_path") else None,
                }
                mapping.setdefault(cid, []).append(img)
            return mapping

    try:
        image_map = await asyncio.to_thread(_run)
    except Exception as e:
        logger.warning("章节图片关联失败: %s", e)
        return sections

    enriched = []
    for section in sections:
        cid = section.get("chunk_id", "")
        imgs = image_map.get(cid, [])
        enriched.append({**section, "section_images": imgs})
    return enriched


async def multimodal_search(
    driver,
    question: str,
    strategy: str = "parallel",
    top_k: int = 8,
    use_hyde: bool = False,
    hyde_alpha: float = 0.5,
    doc_id: str = "",
) -> tuple[list[dict], dict[str, float], list[dict], dict[str, Any]]:
    """
    图文混合检索。

    Returns:
        (sections, ft_score_map, caption_images, expansion_info)
        sections 中每项包含 section_images 字段
    """
    from ...routers.query.core import do_retrieval

    # 1. 文字检索（走标准 parallel 策略）
    actual_strategy = "parallel" if strategy == "multimodal" else strategy
    sections, ft_score_map, expansion_info = await asyncio.to_thread(
        do_retrieval,
        driver, question, actual_strategy, top_k,
        use_hyde, hyde_alpha, doc_id, True,
    )

    # 2. 从检索结果中提取 doc_ids，用于图片检索范围限定
    doc_ids = list(dict.fromkeys(
        s.get("doc_id", "") for s in sections if s.get("doc_id")
    ))

    # 3. 并行：章节图片关联 + caption 图片检索
    enriched_sections, caption_images = await asyncio.gather(
        _attach_section_images(driver, sections),
        _caption_search(driver, question, doc_ids),
    )

    logger.info(
        "multimodal_search: sections=%d section_images=%d caption_images=%d",
        len(enriched_sections),
        sum(len(s.get("section_images", [])) for s in enriched_sections),
        len(caption_images),
    )
    return enriched_sections, ft_score_map, caption_images, expansion_info
