"""
文档重新处理服务 — 对已入库文档执行新数据处理管道

支持管道:
    entities   — 重新提取工具/材料/工序实体
    constraints — 重新提取文本约束节点（LLM）
    tables     — PP-Structure 表格 → Constraint 节点
    drawings   — 图片 → 工程图纸专项分析
    defects    — 图片 → 缺陷检测 → Defect 节点
"""
import logging
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")


# ── 辅助 ──────────────────────────────────────────────────────────────────────

def find_pdf(doc_id: str) -> Path | None:
    """在 uploads/ 目录中查找文档对应的 PDF 文件"""
    candidates = (
        sorted(UPLOAD_DIR.glob(f"{doc_id}*.pdf")) +
        sorted(UPLOAD_DIR.glob(f"{doc_id}*.PDF"))
    )
    return candidates[0] if candidates else None


def load_sections(driver, doc_id: str) -> list[dict]:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id AS chunk_id,
                   s.number   AS number,
                   s.title    AS title,
                   s.content  AS content
            ORDER BY s.number
        """, doc_id=doc_id)
        return [dict(r) for r in result]


def load_images(driver, doc_id: str) -> list[dict]:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            OPTIONAL MATCH (s)-[:HAS_IMAGE]->(i:Image)
            WHERE i IS NOT NULL
            RETURN i.image_id  AS image_id,
                   i.path      AS path,
                   i.caption   AS caption,
                   i.is_drawing AS is_drawing
        """, doc_id=doc_id)
        return [dict(r) for r in result]


# ── 各管道实现 ─────────────────────────────────────────────────────────────────

def _run_entities(driver, doc_id: str, sections: list[dict], step: Callable):
    step("entities", "重新提取工具/材料/工序实体...")
    from .entity_extractor import extract_entities_from_sections
    from .entity_writer    import write_entities
    entities = extract_entities_from_sections(sections)
    write_entities(driver, doc_id, entities)
    return len(entities) if isinstance(entities, list) else 0


def _run_constraints(driver, doc_id: str, sections: list[dict], step: Callable):
    step("constraints", "重新提取文本约束参数...")
    from .entity_extractor import extract_constraints_from_sections
    from .entity_writer    import write_constraints
    constraints = extract_constraints_from_sections(sections)
    write_constraints(driver, doc_id, constraints)
    return len(constraints) if isinstance(constraints, list) else 0


def _run_tables(driver, doc_id: str, pdf_path: Path, sections: list[dict], step: Callable):
    step("tables", "PP-Structure 表格提取...")
    from .table_extractor import extract_all_tables, is_available
    from .entity_writer   import write_constraints
    if not is_available():
        logger.warning("PaddleOCR 未安装，跳过表格提取")
        return 0
    table_cons = extract_all_tables(str(pdf_path), doc_id, sections)
    if table_cons:
        write_constraints(driver, doc_id, table_cons)
    return len(table_cons)


def _run_drawings(driver, doc_id: str, images: list[dict], step: Callable):
    import json
    from .drawing_analyzer import analyze_drawing, is_likely_drawing
    from .entity_writer    import write_drawing_constraints

    step("drawings", f"分析 {len(images)} 张图片中的工程图纸...")
    count = 0
    for img in images:
        if not img.get("path"):
            continue
        try:
            result = analyze_drawing(img["path"], img.get("caption") or "", doc_id)
            with driver.session() as session:
                session.run("""
                    MATCH (i:Image {image_id: $image_id})
                    SET i.is_drawing         = $is_drawing,
                        i.part_numbers       = $part_numbers,
                        i.annotations        = $annotations,
                        i.assembly_relations = $assembly_relations,
                        i.drawing_summary    = $summary
                """,
                    image_id          = img["image_id"],
                    is_drawing        = result.get("is_drawing", False),
                    part_numbers      = json.dumps(result.get("part_numbers", []), ensure_ascii=False),
                    annotations       = json.dumps(result.get("annotations", []), ensure_ascii=False),
                    assembly_relations= json.dumps(result.get("assembly_relations", []), ensure_ascii=False),
                    summary           = result.get("summary", ""),
                )
            if result.get("annotations"):
                write_drawing_constraints(driver, img["image_id"], doc_id, result["annotations"])
            count += 1
        except Exception as e:
            logger.warning("图纸分析失败 image_id=%s: %s", img["image_id"], e)
    return count


def _run_defects(driver, doc_id: str, images: list[dict], step: Callable):
    from .defect_detector import detect_defects, detect_defects_vlm, is_available
    from .defect_writer   import write_defects_batch

    step("defects", f"对 {len(images)} 张图片进行缺陷检测...")
    total = 0
    for img in images:
        if not img.get("path"):
            continue
        try:
            defects = detect_defects(img["path"]) if is_available() else []
            if not defects:
                defects = detect_defects_vlm(img["path"], doc_id)
            if defects:
                write_defects_batch(driver, img["image_id"], doc_id, defects)
                total += len(defects)
        except Exception as e:
            logger.warning("缺陷检测失败 image_id=%s: %s", img["image_id"], e)
    return total


# ── 主编排函数 ────────────────────────────────────────────────────────────────

def reprocess_document(
    doc_id:    str,
    driver,
    pipelines: list[str],
    task:      dict,
) -> None:
    """
    同步执行所有选定管道（在 asyncio.to_thread 中调用）。
    task 字典由调用者创建，函数负责更新其状态字段。
    """
    task["status"] = "running"
    task["started_at"] = int(time.time())

    def step(name: str, msg: str):
        task["current"] = name
        task["message"] = msg
        logger.info("[reprocess %s] %s", doc_id, msg)

    try:
        sections = load_sections(driver, doc_id)
        images   = load_images(driver, doc_id)
        pdf_path = find_pdf(doc_id)

        results: dict[str, int] = {}

        for pipeline in pipelines:
            try:
                if pipeline == "entities":
                    results["entities"] = _run_entities(driver, doc_id, sections, step)
                elif pipeline == "constraints":
                    results["constraints"] = _run_constraints(driver, doc_id, sections, step)
                elif pipeline == "tables":
                    if pdf_path:
                        results["tables"] = _run_tables(driver, doc_id, pdf_path, sections, step)
                    else:
                        logger.warning("未找到 PDF 文件，跳过表格提取: %s", doc_id)
                        results["tables"] = 0
                elif pipeline == "drawings":
                    results["drawings"] = _run_drawings(driver, doc_id, images, step)
                elif pipeline == "defects":
                    results["defects"] = _run_defects(driver, doc_id, images, step)
            except Exception as e:
                logger.warning("[reprocess %s] 管道 %s 失败: %s", doc_id, pipeline, e)
                results[pipeline] = -1

        task.update({"status": "completed", "results": results,
                     "current": "", "message": "处理完成",
                     "finished_at": int(time.time())})
    except Exception as e:
        logger.error("[reprocess %s] 总体失败: %s", doc_id, e)
        task.update({"status": "failed", "error": str(e),
                     "finished_at": int(time.time())})
