from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from .reprocess_pipelines import (
    _run_constraints,
    _run_defects,
    _run_drawings,
    _run_entities,
    _run_images,
    _run_reparse,
    _run_vectorize,
    _run_tables,
)
from .reprocess_support import cancelled as _cancelled, find_pdf, load_images, load_sections

logger = logging.getLogger(__name__)


def reprocess_document(
    doc_id: str,
    driver,
    pipelines: list[str],
    task: dict,
    on_step: Callable[[str, str], None] | None = None,
) -> None:
    task.update({"status": "running", "started_at": int(time.time())})

    def step(name: str, msg: str):
        task.update({"current": name, "message": msg})
        logger.info("[reprocess %s] %s", doc_id, msg)
        if on_step:
            on_step(name, msg)

    try:
        step("snapshot", "拍摄当前状态快照...")
        try:
            from .snapshot_service import take_snapshot

            sid = take_snapshot(driver, doc_id)
            task["snapshot_id"] = sid
        except Exception as e:
            logger.warning("快照失败（继续处理）: %s", e)

        sections = load_sections(driver, doc_id)
        images = load_images(driver, doc_id)
        source_path = find_pdf(doc_id)
        extract_pdf_path = source_path
        cleanup_paths: list[Path] = []
        results: dict[str, int] = {}

        pipeline_order = ["reparse", "vectorize", "images", "entities", "constraints", "tables", "drawings", "defects"]
        ordered_pipelines = sorted(
            pipelines,
            key=lambda pipeline: pipeline_order.index(pipeline) if pipeline in pipeline_order else 999,
        )

        for pipeline in ordered_pipelines:
            if _cancelled(task):
                task.update(
                    {
                        "status": "cancelled",
                        "current": "",
                        "message": "已被中止",
                        "finished_at": int(time.time()),
                    }
                )
                return

            if pipeline != "reparse" and results.get("reparse", -1) >= 0:
                sections = load_sections(driver, doc_id)
                images = load_images(driver, doc_id)

            try:
                if pipeline == "reparse":
                    count, extract_pdf_path, new_cleanup = _run_reparse(
                        driver, doc_id, source_path, task, step
                    )
                    results[pipeline] = count
                    for path in new_cleanup:
                        if path and path not in cleanup_paths:
                            cleanup_paths.append(path)
                elif pipeline == "vectorize":
                    results[pipeline] = _run_vectorize(driver, doc_id, task, step)
                elif pipeline == "images":
                    if not extract_pdf_path:
                        from .reprocess_support import prepare_reprocess_pdf as _prepare_reprocess_pdf

                        extract_pdf_path, new_cleanup = _prepare_reprocess_pdf(doc_id, source_path, driver)
                        for path in new_cleanup:
                            if path and path not in cleanup_paths:
                                cleanup_paths.append(path)
                    results[pipeline] = (
                        _run_images(driver, doc_id, extract_pdf_path, sections, task, step)
                        if extract_pdf_path
                        else 0
                    )
                elif pipeline == "entities":
                    results[pipeline] = _run_entities(driver, doc_id, sections, task, step)
                elif pipeline == "constraints":
                    results[pipeline] = _run_constraints(driver, doc_id, sections, task, step)
                elif pipeline == "tables":
                    if not extract_pdf_path:
                        from .reprocess_support import prepare_reprocess_pdf as _prepare_reprocess_pdf

                        extract_pdf_path, new_cleanup = _prepare_reprocess_pdf(doc_id, source_path, driver)
                        for path in new_cleanup:
                            if path and path not in cleanup_paths:
                                cleanup_paths.append(path)
                    results[pipeline] = (
                        _run_tables(driver, doc_id, extract_pdf_path, sections, task, step)
                        if extract_pdf_path
                        else 0
                    )
                elif pipeline == "drawings":
                    results[pipeline] = _run_drawings(driver, doc_id, images, task, step)
                elif pipeline == "defects":
                    results[pipeline] = _run_defects(driver, doc_id, images, task, step)
            except Exception as e:
                logger.warning("[reprocess %s] 管道 %s 失败: %s", doc_id, pipeline, e)
                results[pipeline] = -1

        final_status = "cancelled" if _cancelled(task) else "completed"
        task.update(
            {
                "status": final_status,
                "results": results,
                "current": "",
                "message": "完成" if final_status == "completed" else "已中止",
                "finished_at": int(time.time()),
            }
        )
    except Exception as e:
        logger.error("[reprocess %s] 总体失败: %s", doc_id, e)
        task.update({"status": "failed", "error": str(e), "finished_at": int(time.time())})
    finally:
        for path in locals().get("cleanup_paths", []):
            try:
                if path and path.exists():
                    path.unlink(missing_ok=True)
            except Exception as cleanup_exc:
                logger.warning("[reprocess %s] 清理临时文件失败 %s: %s", doc_id, path, cleanup_exc)
