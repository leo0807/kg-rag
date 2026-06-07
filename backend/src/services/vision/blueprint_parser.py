"""
src/services/vision/blueprint_parser.py
工程图纸深度解析器 — 将 drawing_analyzer 的输出转换为结构化 JSON。

输入：图纸图片路径（或 PDF 中的某页提取图片）
输出：BlueprintResult 结构体，包含 parts/fasteners/key_dimensions/
      process_requirements/annotations/raw_text
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# 判断标注属于紧固件的关键词
_FASTENER_KEYWORDS = frozenset([
    "铆钉", "螺栓", "螺钉", "螺母", "销", "rivet", "bolt", "screw", "nut", "pin",
    "ms204", "ms20", "nas", "as3"
])

# 判断标注属于尺寸的类型
_DIMENSION_TYPES = frozenset(["tolerance", "dimension"])


@dataclass
class PartInfo:
    part_no:        str
    material:       str = ""
    quantity:       int = 1
    specifications: str = ""


@dataclass
class FastenerInfo:
    type:      str
    spec:      str = ""
    quantity:  int = 0
    position:  str = ""


@dataclass
class DimensionInfo:
    name:      str
    value:     str
    tolerance: str = ""
    unit:      str = ""


@dataclass
class BlueprintResult:
    drawing_id:          str
    title:               str = ""
    is_drawing:          bool = False
    parts:               list[PartInfo]    = field(default_factory=list)
    fasteners:           list[FastenerInfo] = field(default_factory=list)
    key_dimensions:      list[DimensionInfo] = field(default_factory=list)
    process_requirements: list[str]         = field(default_factory=list)
    annotations:         list[dict]         = field(default_factory=list)
    raw_text:            str               = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["parts"]          = [asdict(p) for p in self.parts]
        d["fasteners"]      = [asdict(f) for f in self.fasteners]
        d["key_dimensions"] = [asdict(k) for k in self.key_dimensions]
        return d


def _extract_cps_refs(text: str) -> list[str]:
    """从文本中提取 CPS/AMS/MS 规范引用。"""
    return list(dict.fromkeys(re.findall(
        r"(?:CPS|AMS|MIL-|MS|NAS|AS)\s*\d[\d\-\.]*",
        text, re.IGNORECASE,
    )))


def _annotations_to_fasteners(annotations: list[dict]) -> list[FastenerInfo]:
    fasteners = []
    for ann in annotations:
        raw = (ann.get("raw") or "").lower()
        param = (ann.get("parameter") or "").lower()
        if any(kw in raw or kw in param for kw in _FASTENER_KEYWORDS):
            fasteners.append(FastenerInfo(
                type     = ann.get("parameter") or ann.get("raw") or "紧固件",
                spec     = ann.get("raw", ""),
                quantity = 0,
                position = "",
            ))
    return fasteners


def _annotations_to_dimensions(annotations: list[dict]) -> list[DimensionInfo]:
    dims = []
    for ann in annotations:
        atype = (ann.get("type") or "").lower()
        if atype in _DIMENSION_TYPES:
            tol = ""
            if ann.get("value_max") or ann.get("value_min"):
                tol = f"+{ann.get('value_max', '')}/-{ann.get('value_min', '')}"
            dims.append(DimensionInfo(
                name      = ann.get("parameter") or ann.get("type", ""),
                value     = str(ann.get("value") or ""),
                tolerance = tol,
                unit      = ann.get("unit") or "",
            ))
    return dims


def _extract_process_requirements(summary: str, annotations: list[dict]) -> list[str]:
    """从 summary 和标注中提取工艺要求和规范引用。"""
    reqs: list[str] = []
    # CPS 等规范引用
    all_text = summary + " " + " ".join(ann.get("raw", "") for ann in annotations)
    cps_refs = _extract_cps_refs(all_text)
    for ref in cps_refs:
        reqs.append(f"按 {ref} 执行")
    # 表面粗糙度、公差要求
    for ann in annotations:
        if (ann.get("type") or "").lower() == "surface":
            reqs.append(f"表面粗糙度要求: {ann.get('raw', '')}")
    # summary 中的工艺关键词句
    for kw in ("密封", "固化", "扭矩", "清洁", "检验", "涂覆"):
        for sent in summary.split("。"):
            if kw in sent:
                clean = sent.strip()
                if clean and clean not in reqs:
                    reqs.append(clean)
                break
    return reqs[:10]


def parse_blueprint(
    image_path: str,
    drawing_id: str = "",
    caption:    str = "",
    doc_id:     str = "",
) -> BlueprintResult:
    """
    解析工程图纸图片，返回结构化 BlueprintResult。

    内部复用 drawing_analyzer.analyze_drawing() 完成 VLM 调用，
    本函数只做结果映射和补充提取。
    """
    from ..images.drawing_analyzer import analyze_drawing

    did = drawing_id or Path(image_path).stem

    try:
        raw = analyze_drawing(image_path, caption=caption, doc_id=doc_id)
    except Exception as e:
        logger.warning("drawing_analyzer 失败 %s: %s", image_path, e)
        return BlueprintResult(drawing_id=did)

    if raw.get("analysis_level") == "skipped":
        logger.info("图片规则过滤跳过 %s: %s", image_path, raw.get("skip_reason"))
        return BlueprintResult(drawing_id=did, raw_text=caption)

    annotations = raw.get("annotations") or []
    summary     = raw.get("summary") or caption

    # parts: 从 part_numbers 构建
    parts = [
        PartInfo(part_no=str(pn)) for pn in (raw.get("part_numbers") or []) if pn
    ]

    # fasteners: 从 annotations 中提取
    fasteners = _annotations_to_fasteners(annotations)

    # key_dimensions: 从 annotations 中提取尺寸标注
    key_dims = _annotations_to_dimensions(annotations)

    # process_requirements: 从 summary + annotations 提取
    proc_reqs = _extract_process_requirements(summary, annotations)

    # raw_text: summary + 所有标注的 raw 字段
    raw_parts = [ann.get("raw", "") for ann in annotations if ann.get("raw")]
    raw_text = summary + ("\n" + "\n".join(raw_parts) if raw_parts else "")

    result = BlueprintResult(
        drawing_id           = did,
        title                = summary[:60],
        is_drawing           = bool(raw.get("is_drawing")),
        parts                = parts,
        fasteners            = fasteners,
        key_dimensions       = key_dims,
        process_requirements = proc_reqs,
        annotations          = annotations,
        raw_text             = raw_text,
    )
    logger.info(
        "蓝图解析完成 %s: is_drawing=%s parts=%d fasteners=%d dims=%d",
        did, result.is_drawing, len(parts), len(fasteners), len(key_dims),
    )
    return result


def parse_blueprint_from_pdf(
    pdf_path: str,
    page_idx: int = 0,
    drawing_id: str = "",
    doc_id: str = "",
) -> BlueprintResult:
    """从 PDF 的指定页面提取图片并解析。"""
    import tempfile
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF 未安装，无法解析 PDF 图纸")
        return BlueprintResult(drawing_id=drawing_id or pdf_path)

    try:
        doc = fitz.open(pdf_path)
        if page_idx >= len(doc):
            page_idx = 0
        page = doc[page_idx]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x 分辨率
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            pix.save(tmp.name)
            img_path = tmp.name
        doc.close()
        return parse_blueprint(
            img_path,
            drawing_id=drawing_id or f"{Path(pdf_path).stem}_p{page_idx}",
            doc_id=doc_id,
        )
    except Exception as e:
        logger.error("PDF 图纸解析失败 %s: %s", pdf_path, e)
        return BlueprintResult(drawing_id=drawing_id or pdf_path)
