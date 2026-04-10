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
UPLOAD_DIR = Path("uploads")


# ── 辅助 ──────────────────────────────────────────────────────────────────────

def find_pdf(doc_id: str) -> Path | None:
    candidates = (sorted(UPLOAD_DIR.glob(f"{doc_id}*.pdf")) +
                  sorted(UPLOAD_DIR.glob(f"{doc_id}*.PDF")))
    return candidates[0] if candidates else None


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
    entities = extract_entities_from_sections(sections)
    write_entities(driver, doc_id, entities)
    return len(entities) if isinstance(entities, list) else 0


def _run_constraints(driver, doc_id, sections, task, step):
    step("constraints", "重新提取文本约束参数...")
    if _cancelled(task): return -1
    from .entity_extractor import extract_constraints_from_sections
    from .entity_writer    import write_constraints
    data = extract_constraints_from_sections(sections)
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
    from .drawing_analyzer import analyze_drawing
    from .entity_writer    import write_drawing_constraints
    step("drawings", f"分析 {len(images)} 张图片中的工程图纸...")
    count = 0
    for img in images:
        if _cancelled(task): break
        if not img.get("path"): continue
        try:
            result = analyze_drawing(img["path"], img.get("caption") or "", doc_id)
            with driver.session() as s:
                s.run("""MATCH (i:Image {image_id:$iid})
                    SET i.is_drawing=$is_d, i.part_numbers=$pn,
                        i.annotations=$ann, i.assembly_relations=$ar, i.drawing_summary=$ds""",
                    iid=img["image_id"], is_d=result.get("is_drawing", False),
                    pn=json.dumps(result.get("part_numbers",[]),ensure_ascii=False),
                    ann=json.dumps(result.get("annotations",[]),ensure_ascii=False),
                    ar=json.dumps(result.get("assembly_relations",[]),ensure_ascii=False),
                    ds=result.get("summary",""),
                )
            if result.get("annotations"):
                write_drawing_constraints(driver, img["image_id"], doc_id, result["annotations"])
            count += 1
        except Exception as e:
            logger.warning("图纸分析失败 %s: %s", img["image_id"], e)
    return count


def _run_defects(driver, doc_id, images, task, step):
    from .defect_detector import detect_defects, detect_defects_vlm, is_available
    from .defect_writer   import write_defects_batch
    step("defects", f"对 {len(images)} 张图片进行缺陷检测...")
    total = 0
    for img in images:
        if _cancelled(task): break
        if not img.get("path"): continue
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

def reprocess_document(doc_id: str, driver, pipelines: list[str], task: dict) -> None:
    """
    同步执行所有选定管道（在 asyncio.to_thread 中调用）。
    处理前自动拍摄快照，支持 task["cancel_requested"] 中止。
    """
    task.update({"status": "running", "started_at": int(time.time())})

    def step(name: str, msg: str):
        task.update({"current": name, "message": msg})
        logger.info("[reprocess %s] %s", doc_id, msg)

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

        _RUNNERS = {
            "entities":    lambda: _run_entities(driver, doc_id, sections, task, step),
            "constraints": lambda: _run_constraints(driver, doc_id, sections, task, step),
            "tables":      lambda: _run_tables(driver, doc_id, pdf_path, sections, task, step) if pdf_path else 0,
            "drawings":    lambda: _run_drawings(driver, doc_id, images, task, step),
            "defects":     lambda: _run_defects(driver, doc_id, images, task, step),
        }

        for pipeline in pipelines:
            if _cancelled(task):
                task.update({"status": "cancelled", "current": "", "message": "已被中止",
                             "finished_at": int(time.time())})
                return
            runner = _RUNNERS.get(pipeline)
            if runner:
                try:
                    results[pipeline] = runner()
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
