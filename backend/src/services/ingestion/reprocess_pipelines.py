from __future__ import annotations

import json
import logging
from pathlib import Path

from .reprocess_support import (
    cancelled as _cancelled,
    download_from_minio,
    find_pdf,
    get_storage_key,
    resolve_drawing_image_path as _resolve_drawing_image_path,
)
from .reprocess_vectorize import _run_vectorize as _run_vectorize_impl

logger = logging.getLogger(__name__)


def _run_entities(driver, doc_id, sections, task, step):
    step("entities", "重新提取工具/材料/工序实体...")
    if _cancelled(task):
        return -1
    from ..graph.entity_extractor import extract_entities_from_sections
    from ..graph.entity_writer import reset_document_entity_graph, write_entities

    def on_prog(i, n):
        step("entities", f"正在提取实体: {i}/{n} 章节...")

    reset_document_entity_graph(driver, doc_id)
    entities = extract_entities_from_sections(sections, on_progress=on_prog)
    write_entities(driver, doc_id, entities)
    return len(entities) if isinstance(entities, list) else 0


def _run_constraints(driver, doc_id, sections, task, step):
    step("constraints", "重新提取文本约束参数...")
    if _cancelled(task):
        return -1
    from ..graph.entity_extractor import extract_constraints_from_sections
    from ..graph.entity_writer import reset_document_text_constraints, write_constraints

    def on_prog(i, n):
        step("constraints", f"正在提取约束: {i}/{n} 章节...")

    reset_document_text_constraints(driver, doc_id)
    data = extract_constraints_from_sections(sections, on_progress=on_prog)
    write_constraints(driver, doc_id, data)
    return len(data) if isinstance(data, list) else 0


def _run_images(driver, doc_id, pdf_path, sections, task, step):
    step("images", "重新提取图片节点...")
    if _cancelled(task):
        return -1
    try:
        from .backfill_service import extract_images_for_doc, _delete_existing_images_for_doc

        cleanup_paths: list[Path] = []
        image_source = find_pdf(doc_id)
        if not image_source:
            storage_key = get_storage_key(driver, doc_id)
            if storage_key:
                image_source = download_from_minio(doc_id, storage_key)
                if image_source:
                    cleanup_paths.append(image_source)
        image_source = image_source or Path(pdf_path)
        deleted = _delete_existing_images_for_doc(doc_id, driver)
        if deleted:
            step("images", f"已清理 {deleted} 张旧图片，开始按新规则重新提取...")
        count = extract_images_for_doc(doc_id, Path(image_source), sections, driver)
        for cleanup_path in cleanup_paths:
            cleanup_path.unlink(missing_ok=True)
        return count
    except Exception as e:
        logger.warning("[reprocess %s] 图片提取失败: %s", doc_id, e)
        return -1


def _run_tables(driver, doc_id, pdf_path, sections, task, step):
    step("tables", "PP-Structure 表格提取...")
    if _cancelled(task):
        return -1
    from ..graph.entity_writer import reset_document_tables, write_tables
    from ..tables.table_extractor import extract_tables_full, is_available

    if not is_available():
        return 0
    reset_document_tables(driver, doc_id)
    tables = extract_tables_full(str(pdf_path), doc_id, sections)
    if tables:
        write_tables(driver, doc_id, tables)
    return len(tables)


def _run_drawings(driver, doc_id, images, task, step):
    import time as _time

    from ..graph.entity_writer import write_drawing_constraints
    from ..images.drawing_analyzer import analyze_drawing
    from ..storage.milvus_store import delete_image_vectors

    total_imgs = len(images)
    step("drawings", f"准备分析 {total_imgs} 张图片中的工程图纸...")
    delete_image_vectors(doc_id)
    with driver.session() as s:
        s.run(
            """
            MATCH (:Document {name: $doc_id})-[:HAS_IMAGE]->(i:Image)
            SET i.is_drawing = false
            REMOVE i.analyzed_at, i.analysis_level, i.skip_reason,
                   i.part_numbers, i.annotations, i.assembly_relations,
                   i.drawing_summary, i.table_data, i.formula_data
            """,
            doc_id=doc_id,
        )
        s.run(
            """
            MATCH (c:Constraint {doc_id: $doc_id, source: 'drawing'})
            DETACH DELETE c
            """,
            doc_id=doc_id,
        )
    count = 0
    failed = 0

    for idx, img in enumerate(images, start=1):
        if _cancelled(task):
            break

        image_id = img.get("image_id", f"img_{idx}")
        cleanup_path = None

        try:
            image_path, cleanup_path = _resolve_drawing_image_path(
                image_id=image_id,
                local_path=img.get("path"),
                minio_path=img.get("minio_path"),
            )
            step("drawings", f"正在分析图纸 ({idx}/{total_imgs}): {image_path.name}...")
            result = analyze_drawing(str(image_path), img.get("caption") or "", doc_id)
            caption = (result.get("summary") or img.get("caption") or "").strip()
            analyzed_at = int(_time.time())

            with driver.session() as s:
                s.run(
                    """MATCH (i:Image {image_id: $iid})
                       SET i.is_drawing         = $is_d,
                           i.caption            = $caption,
                           i.analyzed_at        = $analyzed_at,
                           i.analysis_level     = $level,
                           i.skip_reason        = $skip_reason,
                           i.part_numbers       = $pn,
                           i.annotations        = $ann,
                           i.assembly_relations = $ar,
                           i.drawing_summary    = $ds,
                           i.table_data         = $td,
                           i.formula_data       = $fd""",
                    iid=image_id,
                    is_d=result.get("is_drawing", False),
                    caption=caption,
                    analyzed_at=analyzed_at,
                    level=result.get("analysis_level", "basic"),
                    skip_reason=result.get("skip_reason"),
                    pn=json.dumps(result.get("part_numbers", []), ensure_ascii=False),
                    ann=json.dumps(result.get("annotations", []), ensure_ascii=False),
                    ar=json.dumps(result.get("assembly_relations", []), ensure_ascii=False),
                    ds=result.get("summary", ""),
                    td=(json.dumps(result["table_data"], ensure_ascii=False) if result.get("table_data") else None),
                    fd=(json.dumps(result["formula_data"], ensure_ascii=False) if result.get("formula_data") else None),
                )

            if result.get("annotations"):
                write_drawing_constraints(driver, image_id, doc_id, result["annotations"])

            if caption and result.get("analysis_level") != "skipped":
                try:
                    from ..images.image_vector_service import build_image_milvus_text
                    from ..retrieval.embedder import embed_texts
                    from ..storage.milvus_store import upsert_sections

                    milvus_text = build_image_milvus_text(
                        summary=caption,
                        part_numbers=result.get("part_numbers"),
                        assembly_relations=result.get("assembly_relations"),
                    )

                    if not milvus_text:
                        continue

                    embeddings = embed_texts([milvus_text])
                    if embeddings and embeddings[0]:
                        chunk_id = f"{doc_id}_img_{image_id}"
                        upsert_sections(
                            [
                                {
                                    "chunk_id": chunk_id,
                                    "doc_id": doc_id,
                                    "text": milvus_text,
                                    "embedding": embeddings[0],
                                }
                            ]
                        )
                        logger.info("图片向量已写入 Milvus chunk_id=%s", chunk_id)
                except Exception as me:
                    logger.warning("图片 Milvus 写入失败 %s: %s", image_id, me)

            count += 1

        except Exception as e:
            failed += 1
            logger.warning("图纸分析失败 image_id=%s 原因: %s", image_id, e)
        finally:
            if cleanup_path:
                cleanup_path.unlink(missing_ok=True)

    logger.info(
        "图纸分析完成 doc_id=%s 成功=%d 失败=%d 总=%d",
        doc_id,
        count,
        failed,
        total_imgs,
    )
    return count


def _run_reparse(driver, doc_id, pdf_path, task, step):
    step("reparse", "重新解析文档提取章节结构...")
    cleanup_paths: list[Path] = []
    source_path = pdf_path
    from .reprocess_support import prepare_reprocess_pdf as _prepare_reprocess_pdf

    prepared_pdf, prepared_cleanup = _prepare_reprocess_pdf(doc_id, source_path, driver)
    cleanup_paths.extend(prepared_cleanup)
    if not prepared_pdf:
        logger.warning("[reparse %s] 未找到文档文件，跳过", doc_id)
        return 0, None, cleanup_paths

    from ..graph.entity_writer import cleanup_stale_document_nodes
    from ..graph.neo4j_writer import rewrite_sections
    from ..parsing.parser import parse

    doc = parse(prepared_pdf if prepared_pdf.suffix.lower() == ".pdf" else source_path or prepared_pdf)
    effective_pdf = doc.pdf_path if doc and doc.pdf_path and doc.pdf_path.exists() else prepared_pdf
    if doc and doc.pdf_path and doc.pdf_path not in cleanup_paths and doc.pdf_path != source_path:
        cleanup_paths.append(doc.pdf_path)

    count = rewrite_sections(driver, doc)
    cleanup_stale_document_nodes(driver, doc_id)
    step("reparse", f"章节重新解析完成，共 {count} 个章节")
    return count, effective_pdf, cleanup_paths


def _run_vectorize(driver, doc_id, task, step):
    return _run_vectorize_impl(driver, doc_id, task, step)


def _run_defects(driver, doc_id, images, task, step):
    from ..quality.defect_detector import detect_defects, detect_defects_vlm, is_available
    from ..quality.defect_writer import write_defects_batch

    total_imgs = len(images)
    step("defects", f"准备对 {total_imgs} 张图片进行缺陷检测...")
    total = 0
    for idx, img in enumerate(images, start=1):
        if _cancelled(task):
            break
        if not img.get("path"):
            continue
        step("defects", f"正在检测缺陷 ({idx}/{total_imgs}): {Path(img['path']).name}...")
        try:
            defects = detect_defects(img["path"]) if is_available() else []
            if not defects:
                defects = detect_defects_vlm(img["path"], doc_id)
            if defects:
                write_defects_batch(driver, img["image_id"], doc_id, defects)
                total += len(defects)
        except Exception as e:
            logger.warning("缺陷检测失败 %s: %s", img["image_id"], e)
    return total
