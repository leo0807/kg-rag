from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

K_TOTAL = "backfill:total"
K_DONE = "backfill:done"
K_CURRENT = "backfill:current"
K_STATUS = "backfill:status"
K_STARTED_AT = "backfill:started_at"
K_PAUSE = "backfill:pause"
K_STOP = "backfill:stop"

_ALL_KEYS = (K_TOTAL, K_DONE, K_CURRENT, K_STATUS, K_STARTED_AT, K_PAUSE, K_STOP)


def _redis():
    from ..infra.cache import get_redis

    return get_redis()


def _get_pending_docs(driver) -> list[str]:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document)
            WHERE d.title IS NOT NULL
              AND NOT (d)-[:HAS_IMAGE]->(:Image)
            RETURN d.name AS doc_id
            ORDER BY d.name ASC
            """
        )
        return [r["doc_id"] for r in result]


def _count_all_docs(driver) -> int:
    with driver.session() as session:
        row = session.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN count(d) AS n"
        ).single()
        return row["n"] if row else 0


def _find_pdf(doc_id: str) -> Optional[Path]:
    for base in (Path("uploads/docs"), Path("uploads")):
        for ext in ("pdf", "PDF", "docx", "DOCX", "doc", "DOC"):
            matches = sorted(base.glob(f"{doc_id}*.{ext}"))
            if matches:
                return matches[0]
    return None


def _delete_existing_images_for_doc(doc_id: str, driver) -> int:
    with driver.session() as session:
        row = session.run(
            """
            MATCH (d:Document {name: $doc_id})-[:HAS_IMAGE]->(i:Image)
            WITH collect(DISTINCT i) AS images
            RETURN size(images) AS count
            """,
            doc_id=doc_id,
        ).single()
        count = int(row["count"]) if row and row["count"] is not None else 0
        if count:
            session.run(
                """
                MATCH (d:Document {name: $doc_id})-[:HAS_IMAGE]->(i:Image)
                WITH collect(DISTINCT i) AS images
                UNWIND images AS image
                DETACH DELETE image
                """,
                doc_id=doc_id,
            )
    if count:
        try:
            from ..storage.milvus_store import delete_image_vectors

            delete_image_vectors(doc_id)
        except Exception as exc:
            logger.warning("[backfill] 删除旧图片向量失败 doc_id=%s: %s", doc_id, exc)
    return count


def _extract_images_for_doc(doc_id: str, pdf_path: Path, sections: list, driver) -> int:
    from ..images.pdf_image_extractor import extract_images_from_document

    page_to_chunk: dict[int, str] = {}
    for section in sections:
        if isinstance(section, dict):
            pidx = section.get("page_idx")
            cid = section.get("chunk_id")
        else:
            pidx = getattr(section, "page_idx", None)
            cid = getattr(section, "chunk_id", None)
        if pidx is not None and cid:
            page_to_chunk[pidx] = cid

    sorted_pages = sorted(page_to_chunk.keys())

    def _find_chunk(page_num: int) -> Optional[str]:
        best = None
        for page in sorted_pages:
            if page <= page_num:
                best = page_to_chunk[page]
            else:
                break
        return best

    extracted_images = extract_images_from_document(str(pdf_path), doc_id, sections)
    image_nodes = [
        {
            "image_id": img.image_id,
            "doc_id": doc_id,
            "page_num": img.page,
            "path": img.path,
            "minio_path": img.minio_key,
            "content_hash": img.content_hash,
            "is_drawing": False,
            "chunk_id": img.chunk_id or _find_chunk(max(int(img.page) - 1, 0)),
        }
        for img in extracted_images
    ]

    if not image_nodes:
        return 0

    with driver.session() as session:
        session.run(
            """
            UNWIND $images AS img
            MATCH (d:Document {name: img.doc_id})
            MERGE (i:Image {image_id: img.image_id})
            SET i.doc_id     = img.doc_id,
                i.page       = img.page_num,
                i.page_num   = img.page_num,
                i.path       = img.path,
                i.minio_path = img.minio_path,
                i.content_hash = img.content_hash,
                i.is_drawing = img.is_drawing
            MERGE (d)-[:HAS_IMAGE]->(i)
            """,
            images=image_nodes,
        )

        section_links = [node for node in image_nodes if node.get("chunk_id")]
        if section_links:
            session.run(
                """
                UNWIND $links AS lnk
                MATCH (s:Section {chunk_id: lnk.chunk_id})
                MATCH (i:Image   {image_id: lnk.image_id})
                MERGE (s)-[:HAS_IMAGE]->(i)
                """,
                links=section_links,
            )

    logger.info("[backfill] 图片写入完成 doc_id=%s count=%d", doc_id, len(image_nodes))
    return len(image_nodes)


def extract_images_for_doc(doc_id: str, pdf_path: Path, sections: list, driver) -> int:
    return _extract_images_for_doc(doc_id, pdf_path, sections, driver)
