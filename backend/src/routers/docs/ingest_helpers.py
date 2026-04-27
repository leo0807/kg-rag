from __future__ import annotations

import asyncio
import logging

from neo4j import Driver

logger = logging.getLogger(__name__)


def _is_logo(img) -> bool:
    w, h = img.width, max(img.height, 1)
    aspect = w / h
    caption = (getattr(img, "caption", "") or "").lower()
    if any(t in caption for t in ["logo", "标志", "徽标", "商标", "公司标识", "公司logo"]):
        return True
    if aspect > 4.0 or aspect < 0.25:
        return True
    if w * h < 200 * 200:
        return True
    if img.page <= 2 and w < 320 and h < 320:
        return True
    return False


async def run_image_analysis(driver: Driver, doc_id: str, pdf_path: str) -> None:
    try:
        from ...services.images.pdf_image_extractor import extract_images_from_pdf
        from ...services.images.image_analyzer import analyze_image_smart
        from ...services.images.multimodal_writer import write_images_to_graph
        from ...services.graph.entity_writer import link_image_tools, write_drawing_constraints

        images = await asyncio.to_thread(extract_images_from_pdf, pdf_path, doc_id)
        images = [img for img in images if not _is_logo(img)]
        if not images:
            return

        analyzed = []
        for img in images:
            try:
                with driver.session() as _sess:
                    hit = _sess.run(
                        "MATCH (i:Image {image_id: $image_id}) "
                        "WHERE i.description IS NOT NULL AND i.description <> '' RETURN i LIMIT 1",
                        image_id=img.image_id,
                    ).single()
                if hit:
                    logger.info("图片已有分析记录，跳过: %s", img.image_id)
                    continue
            except Exception:
                pass

            analysis = await asyncio.to_thread(analyze_image_smart, img.path, img.caption, doc_id)
            drawing: dict = {}
            if analysis.get("task") != "formula":
                from ...services.images.drawing_analyzer import analyze_drawing, is_likely_drawing
                if is_likely_drawing(analysis):
                    try:
                        drawing = await asyncio.to_thread(analyze_drawing, img.path, img.caption, doc_id)
                    except Exception as de:
                        logger.warning("图纸分析失败: %s", de)

            analyzed.append({
                "image_id": img.image_id, "page": img.page, "path": img.path,
                "content_hash": img.content_hash, "minio_key": img.minio_key,
                "caption": img.caption, "analysis": analysis, "drawing": drawing,
            })

        await asyncio.to_thread(write_images_to_graph, driver, doc_id, analyzed)
        for item in analyzed:
            link_image_tools(driver, item["image_id"], item.get("analysis", {}).get("tools", []))
            if anns := item.get("drawing", {}).get("annotations", []):
                write_drawing_constraints(driver, item["image_id"], doc_id, anns)
        logger.info("多模态写入完成 doc_id=%s images=%d", doc_id, len(analyzed))
    except Exception as e:
        logger.warning("多模态处理失败（不影响主流程）: %s", e)
