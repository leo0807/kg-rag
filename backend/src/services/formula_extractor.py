"""
services/formula_extractor.py
从 PDF 页面提取数学公式并转为 LaTeX，写入图谱。
"""
from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

MATH_INDICATORS = [
    "∫", "∑", "∏", "√", "±", "×", "÷",
    "≤", "≥", "≠", "α", "β", "γ", "δ",
    "N·m", "MPa", "°C", "lbf", "sigma", "theta",
]


@lru_cache(maxsize=1)
def _get_model():
    from pix2tex.cli import LatexOCR
    logger.info("加载 pix2tex LatexOCR 模型…")
    return LatexOCR()


def _describe(latex: str) -> str:
    if ("N" in latex and "m" in latex) or "N·m" in latex:
        return "力矩计算公式"
    if "sigma" in latex or "MPa" in latex or "\\sigma" in latex:
        return "应力计算公式"
    if "\\int" in latex or "∫" in latex:
        return "积分计算公式"
    return "工程计算公式"


class FormulaExtractor:
    """扫描 PDF 页面，识别包含数学符号的页并用 pix2tex 提取 LaTeX。"""

    def extract_from_pdf(self, pdf_path: str, doc_id: str) -> list[dict]:
        try:
            import pymupdf
            from PIL import Image
        except ImportError as e:
            logger.error("缺少依赖，公式提取跳过: %s", e)
            return []

        try:
            model = _get_model()
        except Exception as e:
            logger.warning("pix2tex 模型加载失败，公式提取跳过: %s", e)
            return []

        formulas: list[dict] = []
        doc = pymupdf.open(pdf_path)

        for page_num, page in enumerate(doc):
            text = page.extract_text() or ""
            if not any(ind in text for ind in MATH_INDICATORS):
                continue

            try:
                mat = pymupdf.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                latex = model(img)
                if latex and len(latex) > 3:
                    formulas.append({
                        "formula_id": f"{doc_id}_formula_{page_num}",
                        "doc_id": doc_id,
                        "page_num": page_num,
                        "latex": latex.strip(),
                        "description": _describe(latex),
                    })
            except Exception as e:
                logger.warning("公式识别失败 doc=%s 页%d: %s", doc_id, page_num, e)

        doc.close()
        logger.info("公式提取完成 doc=%s 找到=%d", doc_id, len(formulas))
        return formulas
