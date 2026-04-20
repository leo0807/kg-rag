"""
文档重新处理服务 — 对已入库文档执行新数据处理管道

支持管道: entities / constraints / tables / drawings / defects
支持中止（task["cancel_requested"] = True）和快照回滚
"""
import logging
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)
UPLOAD_DIR     = Path("uploads")
DOC_UPLOAD_DIR = Path("uploads") / "docs"   # 新版上传目录


# ── 辅助 ──────────────────────────────────────────────────────────────────────

def find_pdf(doc_id: str) -> Path | None:
    """在 uploads/docs/ 和 uploads/ 两个目录中查找文档文件（PDF/DOCX/DOC）。"""
    exts = ["pdf", "PDF", "docx", "DOCX", "doc", "DOC"]
    for base in (DOC_UPLOAD_DIR, UPLOAD_DIR):
        for ext in exts:
            candidates = sorted(base.glob(f"{doc_id}*.{ext}"))
            if candidates:
                return candidates[0]
    return None


def load_sections(driver, doc_id: str) -> list[dict]:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id AS chunk_id, s.number AS number,
                   s.title AS title, s.content AS content
            ORDER BY s.number
        """, doc_id=doc_id)
        return [dict(r) for r in result]


def load_images(driver, doc_id: str) -> list[dict]:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            OPTIONAL MATCH (s)-[:HAS_IMAGE]->(i:Image)
            WHERE i IS NOT NULL
            RETURN i.image_id AS image_id, i.path AS path,
                   i.caption AS caption, i.is_drawing AS is_drawing
        """, doc_id=doc_id)
        return [dict(r) for r in result]


def _cancelled(task: dict) -> bool:
    return task.get("cancel_requested", False)


# ── 各管道 ────────────────────────────────────────────────────────────────────

def _run_entities(driver, doc_id, sections, task, step):
    step("entities", "重新提取工具/材料/工序实体...")
    if _cancelled(task): return -1
    from .entity_extractor import extract_entities_from_sections
    from .entity_writer    import write_entities
    
    def on_prog(i, n):
        step("entities", f"正在提取实体: {i}/{n} 章节...")
        
    entities = extract_entities_from_sections(sections, on_progress=on_prog)
    write_entities(driver, doc_id, entities)
    return len(entities) if isinstance(entities, list) else 0


def _run_constraints(driver, doc_id, sections, task, step):
    step("constraints", "重新提取文本约束参数...")
    if _cancelled(task): return -1
    from .entity_extractor import extract_constraints_from_sections
    from .entity_writer    import write_constraints
    
    def on_prog(i, n):
        step("constraints", f"正在提取约束: {i}/{n} 章节...")
        
    data = extract_constraints_from_sections(sections, on_progress=on_prog)
    write_constraints(driver, doc_id, data)
    return len(data) if isinstance(data, list) else 0


def _run_tables(driver, doc_id, pdf_path, sections, task, step):
    step("tables", "PP-Structure 表格提取...")
    if _cancelled(task): return -1
    from .table_extractor import extract_all_tables, is_available
    from .entity_writer   import write_constraints
    if not is_available():
        return 0
    cons = extract_all_tables(str(pdf_path), doc_id, sections)
    if cons:
        write_constraints(driver, doc_id, cons)
    return len(cons)


def _run_drawings(driver, doc_id, images, task, step):
    import json
    import time as _time
    from .drawing_analyzer import analyze_drawing
    from .entity_writer    import write_drawing_constraints

    total_imgs = len(images)
    step("drawings", f"准备分析 {total_imgs} 张图片中的工程图纸...")
    count = 0
    failed = 0

    for idx, img in enumerate(images, start=1):
        if _cancelled(task):
            break
        if not img.get("path"):
            continue

        image_id = img.get("image_id", f"img_{idx}")
        step("drawings", f"正在分析图纸 ({idx}/{total_imgs}): {Path(img['path']).name}...")

        try:
            # ── VLM 分析（内部已有 60s 超时和 try/finally 清理） ─────────────
            result = analyze_drawing(img["path"], img.get("caption") or "", doc_id)
            caption     = result.get("summary", "") or img.get("caption", "")
            analyzed_at = int(_time.time())

            # ── 写回 Neo4j Image 节点 ─────────────────────────────────────────
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
                    pn=json.dumps(result.get("part_numbers",  []), ensure_ascii=False),
                    ann=json.dumps(result.get("annotations",  []), ensure_ascii=False),
                    ar=json.dumps(result.get("assembly_relations", []), ensure_ascii=False),
                    ds=result.get("summary", ""),
                    td=(json.dumps(result["table_data"],   ensure_ascii=False)
                        if result.get("table_data")   else None),
                    fd=(json.dumps(result["formula_data"], ensure_ascii=False)
                        if result.get("formula_data") else None),
                )

            # ── 写入标注约束到图谱 ────────────────────────────────────────────
            if result.get("annotations"):
                write_drawing_constraints(driver, image_id, doc_id, result["annotations"])

            # ── 写入 Milvus（skipped 级别无有效内容，跳过） ───────────────────
            if caption.strip() and result.get("analysis_level") != "skipped":
                try:
                    from .embedder      import embed_texts
                    from .milvus_store  import upsert_sections

                    # 组合可检索文本：描述 + 件号 + 装配关系
                    milvus_text = caption
                    if result.get("part_numbers"):
                        milvus_text += "\n件号: " + ", ".join(result["part_numbers"])
                    if result.get("assembly_relations"):
                        milvus_text += "\n装配关系: " + "; ".join(result["assembly_relations"])

                    embeddings = embed_texts([milvus_text])
                    if embeddings and embeddings[0]:
                        chunk_id = f"{doc_id}_img_{image_id}"
                        upsert_sections([{
                            "chunk_id":  chunk_id,
                            "doc_id":    doc_id,
                            "text":      milvus_text,
                            "embedding": embeddings[0],
                        }])
                        logger.info("图片向量已写入 Milvus chunk_id=%s", chunk_id)
                except Exception as me:
                    logger.warning("图片 Milvus 写入失败 %s: %s", image_id, me)

            count += 1

        except Exception as e:
            failed += 1
            logger.warning("图纸分析失败 image_id=%s 原因: %s", image_id, e)

    logger.info(
        "图纸分析完成 doc_id=%s 成功=%d 失败=%d 总=%d",
        doc_id, count, failed, total_imgs,
    )
    return count


def _get_storage_key(driver, doc_id: str) -> str | None:
    """从 Neo4j 读取文档的 MinIO 对象键。"""
    with driver.session() as s:
        r = s.run("MATCH (d:Document {name: $doc_id}) RETURN d.storage_key AS key", doc_id=doc_id)
        row = r.single()
        return row["key"] if row and row["key"] else None


def _download_from_minio(doc_id: str, storage_key: str) -> Path | None:
    """从 MinIO 下载文档到 /tmp，返回本地路径。"""
    try:
        from ..core.storage import download_bytes, BUCKET_RAW_DOCUMENTS
        raw_bytes = download_bytes(BUCKET_RAW_DOCUMENTS, storage_key)
        suffix = Path(storage_key).suffix or ".pdf"
        tmp_path = Path(f"/tmp/{doc_id}_reparse{suffix}")
        tmp_path.write_bytes(raw_bytes)
        logger.info("[reparse %s] 从 MinIO 下载到 %s (%d bytes)", doc_id, tmp_path, len(raw_bytes))
        return tmp_path
    except Exception as e:
        logger.warning("[reparse %s] MinIO 下载失败: %s", doc_id, e)
        return None


def _run_reparse(driver, doc_id, pdf_path, task, step):
    """重新从 PDF/DOCX 解析章节，写回 Neo4j / Milvus / ES。"""
    step("reparse", "重新解析文档提取章节结构...")
    tmp_path = None
    if not pdf_path:
        # 尝试从 MinIO 下载
        storage_key = _get_storage_key(driver, doc_id)
        if storage_key:
            step("reparse", f"本地文件未找到，从 MinIO 下载 {storage_key}...")
            pdf_path = _download_from_minio(doc_id, storage_key)
            tmp_path = pdf_path  # 记录临时文件，稍后清理
        if not pdf_path:
            logger.warning("[reparse %s] 未找到文档文件，跳过", doc_id)
            return 0
    doc = None
    try:
        from .parser import parse
        from .neo4j_writer import rewrite_sections
        doc = parse(pdf_path)
        count = rewrite_sections(driver, doc)
        step("reparse", f"章节重新解析完成，共 {count} 个章节")
        return count
    finally:
        # 清理从 MinIO 下载的原始临时文件
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        # 清理 .doc/.docx 转换生成的临时 PDF（reparse 不提取图片，直接清理）
        if doc is not None and doc.pdf_path and doc.pdf_path != pdf_path:
            doc.pdf_path.unlink(missing_ok=True)


def _run_defects(driver, doc_id, images, task, step):
    from .defect_detector import detect_defects, detect_defects_vlm, is_available
    from .defect_writer   import write_defects_batch
    total_imgs = len(images)
    step("defects", f"准备对 {total_imgs} 张图片进行缺陷检测...")
    total = 0
    for idx, img in enumerate(images, start=1):
        if _cancelled(task): break
        if not img.get("path"): continue
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


# ── 主编排 ────────────────────────────────────────────────────────────────────

def reprocess_document(doc_id: str, driver, pipelines: list[str], task: dict, on_step: Callable[[str, str], None] = None) -> None:
    """
    同步执行所有选定管道（在 asyncio.to_thread 中调用）。
    处理前自动拍摄快照，支持 task["cancel_requested"] 中止。
    """
    task.update({"status": "running", "started_at": int(time.time())})

    def step(name: str, msg: str):
        task.update({"current": name, "message": msg})
        logger.info("[reprocess %s] %s", doc_id, msg)
        if on_step:
            on_step(name, msg)

    try:
        # 处理前快照
        step("snapshot", "拍摄当前状态快照...")
        try:
            from .snapshot_service import take_snapshot
            sid = take_snapshot(driver, doc_id)
            task["snapshot_id"] = sid
        except Exception as e:
            logger.warning("快照失败（继续处理）: %s", e)

        sections = load_sections(driver, doc_id)
        images   = load_images(driver, doc_id)
        pdf_path = find_pdf(doc_id)
        results: dict[str, int] = {}

        # reparse 必须先于其他管道执行（它会更新 sections/images）
        PIPELINE_ORDER = ["reparse", "entities", "constraints", "tables", "drawings", "defects"]
        ordered_pipelines = sorted(
            pipelines,
            key=lambda p: PIPELINE_ORDER.index(p) if p in PIPELINE_ORDER else 999,
        )

        for pipeline in ordered_pipelines:
            if _cancelled(task):
                task.update({"status": "cancelled", "current": "", "message": "已被中止",
                             "finished_at": int(time.time())})
                return

            # 若 reparse 已成功完成，重新加载章节和图片供后续管道使用
            if pipeline != "reparse" and results.get("reparse", -1) >= 0:
                sections = load_sections(driver, doc_id)
                images   = load_images(driver, doc_id)

            try:
                if pipeline == "reparse":
                    results[pipeline] = _run_reparse(driver, doc_id, pdf_path, task, step)
                elif pipeline == "entities":
                    results[pipeline] = _run_entities(driver, doc_id, sections, task, step)
                elif pipeline == "constraints":
                    results[pipeline] = _run_constraints(driver, doc_id, sections, task, step)
                elif pipeline == "tables":
                    results[pipeline] = (_run_tables(driver, doc_id, pdf_path, sections, task, step)
                                         if pdf_path else 0)
                elif pipeline == "drawings":
                    results[pipeline] = _run_drawings(driver, doc_id, images, task, step)
                elif pipeline == "defects":
                    results[pipeline] = _run_defects(driver, doc_id, images, task, step)
            except Exception as e:
                logger.warning("[reprocess %s] 管道 %s 失败: %s", doc_id, pipeline, e)
                results[pipeline] = -1

        final_status = "cancelled" if _cancelled(task) else "completed"
        task.update({"status": final_status, "results": results,
                     "current": "", "message": "完成" if final_status == "completed" else "已中止",
                     "finished_at": int(time.time())})
    except Exception as e:
        logger.error("[reprocess %s] 总体失败: %s", doc_id, e)
        task.update({"status": "failed", "error": str(e), "finished_at": int(time.time())})
