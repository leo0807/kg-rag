"""
src/services/drawing_analyzer.py
工程图纸专项 VLM 分析服务 — 分级处理版

分析层级：
  skipped — 规则过滤（尺寸太小或疑似分隔线），不调用 VLM
  basic   — VLM 判定为非工程图，仅保留描述/summary
  full    — VLM 确认为工程图，完整提取标注 + 表格/公式

调用方负责在 finally 前保证图片文件存在；本模块统一在 finally 中清理。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from ...core.config import settings
from .image_analyzer import image_to_base64
from ..ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# 判断为工程图纸所需的最低置信度（VLM 返回 is_drawing=True）
_DRAWING_ANNOTATION_MIN = 1


# ── 规则预过滤 ────────────────────────────────────────────────────────────────

def _get_image_size(image_path: str) -> tuple[int, int] | None:
    """返回 (width, height)，读取失败返回 None。"""
    try:
        from PIL import Image as _PIL
        with _PIL.open(image_path) as im:
            return im.size
    except Exception:
        return None


def _rule_filter(image_path: str) -> str | None:
    """
    规则预过滤，返回跳过原因（字符串）或 None（不跳过）。

    跳过条件：
    - 两边均 < 200px  → "decorative_size"（图标、装饰图、小logo等）
    - 长宽比 > 5:1    → "likely_separator"（分隔线、页眉横条等）
    """
    size = _get_image_size(image_path)
    if size is None:
        return None  # 无法读取，交给 VLM 处理
    w, h = size
    if w < 200 and h < 200:
        return "decorative_size"
    short = min(w, h)
    if short > 0 and max(w, h) / short > 5.0:
        return "likely_separator"
    return None


# ── 主分析函数 ────────────────────────────────────────────────────────────────

def analyze_drawing(
    image_path: str,
    caption:    str = "",
    doc_id:     str = "",
) -> dict:
    """
    分级图片分析。

    Returns:
        {
            "analysis_level":     "skipped" | "basic" | "full",
            "skip_reason":        str | None,
            "is_drawing":         bool,
            "part_numbers":       [...],
            "annotations":        [...],
            "assembly_relations": [...],
            "summary":            "...",
            "table_data":         {...} | None,   # level=full 且图中有表格
            "formula_data":       {...} | None,   # level=full 且图中有公式
        }
    """
    try:
        # ── Level 0: 规则过滤（零 VLM 调用）────────────────────────────────
        skip_reason = _rule_filter(image_path)
        if skip_reason:
            logger.info("图片规则过滤跳过 %s: %s", Path(image_path).name, skip_reason)
            return {
                "analysis_level":     "skipped",
                "skip_reason":        skip_reason,
                "is_drawing":         False,
                "part_numbers":       [],
                "annotations":        [],
                "assembly_relations": [],
                "summary":            caption or "",
                "table_data":         None,
                "formula_data":       None,
            }

        # ── Level 1: VLM 工程图判断（1 次调用）──────────────────────────────
        ext        = Path(image_path).suffix.lower().lstrip(".")
        media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
        image_b64  = image_to_base64(image_path)

        prompt = f"""你是一位航空机械制图专家。请分析这张图片，判断是否为工程图纸，并提取结构化信息。

图片来源文档：{doc_id}
图片说明：{caption or "无"}

"工程图纸"包括：工程线图、装配图、剖视图、零件图、工艺示意图、液压/电气原理图等含有标注的技术图。
照片、文字截图、条形码等不属于工程图纸。

请严格用JSON格式回答（无多余文字）：
{{
  "is_drawing": true/false,
  "part_numbers": [],
  "annotations": [
    {{
      "type": "tolerance|dimension|surface|other",
      "raw": "原始标注，如 φ12 +0.02/-0.01 或 Ra 1.6",
      "parameter": "参数名，如 孔径/壁厚/表面粗糙度",
      "value": "基准值或标称值",
      "value_max": "最大值，无则空字符串",
      "value_min": "最小值，无则空字符串",
      "unit": "单位如 mm/μm/N·m，无则空字符串"
    }}
  ],
  "assembly_relations": [],
  "summary": "50字以内整体描述"
}}"""

        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }]
        content = get_llm_service().chat(messages, model=settings.VLM_MODEL, timeout=60).strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())

        result.setdefault("part_numbers",       [])
        result.setdefault("annotations",        [])
        result.setdefault("assembly_relations", [])
        result.setdefault("summary",            caption or "")
        result["analysis_level"] = "basic"
        result["skip_reason"]    = None
        result["table_data"]     = None
        result["formula_data"]   = None

        logger.info(
            "图纸分析 Level1 %s: is_drawing=%s annotations=%d",
            Path(image_path).name,
            result.get("is_drawing"),
            len(result.get("annotations", [])),
        )

        # ── Level 2: 完整分析（仅工程图，最多 +2 次 VLM 调用）───────────────
        if result.get("is_drawing"):
            from .vision_service import get_vision_service
            svc = get_vision_service()

            try:
                td = svc.analyze_image(image_path, "table")
                # 仅当模型实际识别到表格内容时记录
                if td.get("headers") or td.get("rows"):
                    result["table_data"] = td
                    logger.info("表格数据已提取 %s: %d 列 %d 行",
                                Path(image_path).name,
                                len(td.get("headers", [])),
                                len(td.get("rows", [])))
            except Exception as te:
                logger.warning("table 分析失败 %s: %s", Path(image_path).name, te)

            try:
                fd = svc.analyze_image(image_path, "formula")
                # 仅当识别到公式时记录
                if fd.get("latex"):
                    result["formula_data"] = fd
                    logger.info("公式已提取 %s: %s", Path(image_path).name, fd.get("latex", "")[:40])
            except Exception as fe:
                logger.warning("formula 分析失败 %s: %s", Path(image_path).name, fe)

            result["analysis_level"] = "full"

        return result

    except Exception as e:
        logger.warning("图纸分析失败 %s: %s", image_path, e)
        return {
            "analysis_level":     "basic",
            "skip_reason":        None,
            "is_drawing":         False,
            "part_numbers":       [],
            "annotations":        [],
            "assembly_relations": [],
            "summary":            caption or "",
            "table_data":         None,
            "formula_data":       None,
        }
    finally:
        # 清理 uploads/images/ 下的临时文件（无论结果如何）
        try:
            p = Path(image_path)
            if p.exists() and "uploads/images" in image_path:
                p.unlink()
                logger.debug("已清理临时图片文件: %s", image_path)
        except Exception as _ce:
            logger.warning("清理临时图片文件失败 %s: %s", image_path, _ce)


def is_likely_drawing(analysis: dict) -> bool:
    """
    根据通用 VLM 分析结果粗判断是否可能为工程图纸，
    用于决定是否值得发起额外的图纸专项分析调用。
    """
    dims     = analysis.get("dimensions", [])
    keywords = " ".join(analysis.get("keywords", []))
    desc     = analysis.get("description", "")
    drawing_hints = ("图纸", "标注", "公差", "剖视", "装配", "零件图",
                     "尺寸", "φ", "±", "Ra", "H7", "h6", "图样")
    text = keywords + desc
    return len(dims) >= _DRAWING_ANNOTATION_MIN or any(h in text for h in drawing_hints)
