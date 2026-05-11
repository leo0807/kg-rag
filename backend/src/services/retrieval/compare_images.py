from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger(__name__)


def figure_labels_from_text(text: str | None) -> list[str]:
    if not text:
        return []
    labels: list[str] = []
    patterns = (
        r"图\s*([0-9]+(?:[-.][0-9]+)+)",
        r"图\s*([0-9]+-\d+)",
        r"Figure\s*([0-9]+-\d+)",
        r"Fig\.?\s*([0-9]+-\d+)",
    )
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            label = f"图{match.replace('.', '-')}"
            if label not in labels:
                labels.append(label)
    return labels


def image_query_terms(topic: str) -> list[str]:
    terms = []
    for token in (topic or "").replace("（", " ").replace("）", " ").split():
        token = token.strip()
        if len(token) >= 2 and token not in terms:
            terms.append(token)
    return terms[:4] or [(topic or "").strip()[:12]]


def attach_figure_labels(images: list[dict], sections: list[dict]) -> list[dict]:
    page_labels: dict[tuple[str, int], list[str]] = {}
    for section in sections:
        doc_id = str(section.get("doc_id") or "").strip()
        labels = figure_labels_from_text(
            " ".join(
                str(section.get(key) or "")
                for key in ("number", "title", "content", "description")
            )
        )
        if not doc_id or not labels:
            continue
        page_candidates = []
        page_idx = section.get("page_idx")
        page_num = section.get("page_num")
        if page_num is not None:
            page_candidates.append(int(page_num))
        if page_idx is not None:
            page_candidates.append(int(page_idx) + 1)
            page_candidates.append(int(page_idx))
        for page in dict.fromkeys([p for p in page_candidates if p >= 0]):
            key = (doc_id, page)
            page_labels.setdefault(key, [])
            for label in labels:
                if label not in page_labels[key]:
                    page_labels[key].append(label)

    enriched: list[dict] = []
    for img in images:
        row = dict(img)
        doc_id = str(row.get("doc_id") or "").strip()
        page_num = row.get("page_num")
        labels: list[str] = []
        if isinstance(page_num, int):
            labels.extend(page_labels.get((doc_id, page_num), []))
        for label in figure_labels_from_text(
            " ".join(
                str(row.get(key) or "")
                for key in ("caption", "description")
            )
        ):
            if label not in labels:
                labels.append(label)
        if labels:
            row["figure_labels"] = labels
            row["figure_label"] = labels[0]
        enriched.append(row)
    return enriched


async def search_images_for_doc(driver, doc_id: str, topic: str, limit: int = 3) -> list[dict]:
    terms = image_query_terms(topic)

    def _run() -> list[dict]:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (i:Image)
                WHERE i.doc_id = $doc_id
                  AND (
                    any(t IN $terms WHERE toLower(coalesce(i.caption, '')) CONTAINS toLower(t))
                    OR any(t IN $terms WHERE toLower(coalesce(i.description, '')) CONTAINS toLower(t))
                    OR any(t IN $terms WHERE toLower(coalesce(coalesce(i.keywords, ''), '')) CONTAINS toLower(t))
                  )
                RETURN
                    i.image_id AS image_id,
                    i.doc_id AS doc_id,
                    coalesce(i.page_num, i.page, 0) AS page_num,
                    i.caption AS caption,
                    i.description AS description,
                    i.minio_path AS minio_path
                ORDER BY coalesce(i.page_num, i.page, 0), i.image_id
                LIMIT $limit
                """,
                doc_id=doc_id,
                terms=terms,
                limit=limit,
            )
            result = [dict(row) for row in rows]
            for row in result:
                minio_path = row.get("minio_path") or ""
                row["url"] = f"/api/images/{row.get('image_id')}" if minio_path else None
                figure_labels = figure_labels_from_text(
                    " ".join(
                        str(row.get(key) or "")
                        for key in ("caption", "description")
                    )
                )
                row["figure_label"] = figure_labels[0] if figure_labels else None
                row["figure_labels"] = figure_labels
            return result

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.debug("比较题图片检索失败 doc_id=%s: %s", doc_id, exc)
        return []


async def search_images_for_sections(
    driver,
    section_ids: list[str],
    limit: int = 3,
) -> list[dict]:
    ids = [sid for sid in dict.fromkeys(section_ids) if sid]
    if not ids:
        return []

    def _run() -> list[dict]:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (s:Section)-[:HAS_IMAGE]->(i:Image)
                WHERE s.chunk_id IN $section_ids
                RETURN
                    i.image_id AS image_id,
                    i.doc_id AS doc_id,
                    coalesce(i.page_num, i.page, 0) AS page_num,
                    i.caption AS caption,
                    i.description AS description,
                    i.minio_path AS minio_path
                ORDER BY coalesce(i.page_num, i.page, 0), i.image_id
                LIMIT $limit
                """,
                section_ids=ids,
                limit=limit,
            )
            result = [dict(row) for row in rows]
            for row in result:
                minio_path = row.get("minio_path") or ""
                row["url"] = f"/api/images/{row.get('image_id')}" if minio_path else None
                figure_labels = figure_labels_from_text(
                    " ".join(
                        str(row.get(key) or "")
                        for key in ("caption", "description")
                    )
                )
                row["figure_label"] = figure_labels[0] if figure_labels else None
                row["figure_labels"] = figure_labels
            return result

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.debug("比较题章节图片检索失败 section_ids=%s: %s", ids[:3], exc)
        return []


async def search_images_for_pages(
    driver,
    doc_id: str,
    pages: list[int],
    limit: int = 3,
) -> list[dict]:
    page_set = [p for p in dict.fromkeys(pages) if isinstance(p, int) and p > 0]
    if not page_set:
        return []

    def _run() -> list[dict]:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (i:Image)
                WHERE i.doc_id = $doc_id
                  AND (
                    coalesce(i.page_num, i.page, 0) IN $pages
                    OR coalesce(i.page_num, i.page, 0) + 1 IN $pages
                  )
                RETURN
                    i.image_id AS image_id,
                    i.doc_id AS doc_id,
                    coalesce(i.page_num, i.page, 0) AS page_num,
                    i.caption AS caption,
                    i.description AS description,
                    i.minio_path AS minio_path
                ORDER BY coalesce(i.page_num, i.page, 0), i.image_id
                LIMIT $limit
                """,
                doc_id=doc_id,
                pages=page_set,
                limit=limit,
            )
            result = [dict(row) for row in rows]
            for row in result:
                minio_path = row.get("minio_path") or ""
                row["url"] = f"/api/images/{row.get('image_id')}" if minio_path else None
                figure_labels = figure_labels_from_text(
                    " ".join(
                        str(row.get(key) or "")
                        for key in ("caption", "description")
                    )
                )
                row["figure_label"] = figure_labels[0] if figure_labels else None
                row["figure_labels"] = figure_labels
            return result

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        logger.debug("比较题页码图片检索失败 doc_id=%s pages=%s: %s", doc_id, page_set[:3], exc)
        return []
