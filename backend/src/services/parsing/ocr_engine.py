"""
增强 OCR 引擎 — 基于 PaddleOCR 的扫描版 PDF 处理

依赖（可选，未安装时自动降级）:
    pip install paddlepaddle paddleocr
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 可选依赖探测 ──────────────────────────────────────────────────────────────
_PADDLE_AVAILABLE = False
_FITZ_AVAILABLE   = False

try:
    import paddleocr as _po   # noqa: F401
    _PADDLE_AVAILABLE = True
except Exception:
    pass

try:
    import fitz as _fitz      # noqa: F401
    _FITZ_AVAILABLE = True
except Exception:
    pass

# 懒初始化单例（避免重复加载模型）
_ocr_instance    = None
_struct_instance = None
_struct_disabled = False
_struct_error_once = False


def is_available() -> bool:
    return _PADDLE_AVAILABLE and _FITZ_AVAILABLE


def is_struct_available() -> bool:
    return is_available() and not _struct_disabled


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        from paddleocr import PaddleOCR
        _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    return _ocr_instance


def _get_struct():
    global _struct_instance
    if _struct_instance is None:
        from paddleocr import PPStructure
        _struct_instance = PPStructure(table=True, ocr=True, show_log=False)
    return _struct_instance


# ── 扫描页检测 ────────────────────────────────────────────────────────────────

def is_scanned_page(page) -> bool:
    """判断 pdfplumber 页面是否为扫描图片页（文字极少且含图片）"""
    text = page.extract_text() or ""
    images = page.images
    return len(text.strip()) < 30 and len(images) > 0


def pdf_has_scanned_pages(pdf_path: str, sample_pages: int = 5) -> bool:
    """采样前 N 页，若 >50% 为扫描页则认为整文档是扫描件"""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[:sample_pages]
            if not pages:
                return False
            scanned = sum(1 for p in pages if is_scanned_page(p))
            return scanned / len(pages) > 0.5
    except Exception as e:
        logger.warning("扫描检测失败: %s", e)
        return False


# ── 页面渲染 ──────────────────────────────────────────────────────────────────

def render_page_to_image(pdf_path: str, page_num: int, dpi: int = 150):
    """
    用 PyMuPDF 将指定页渲染为 numpy array (RGB)。
    返回 numpy.ndarray，失败返回 None。
    """
    if not _FITZ_AVAILABLE:
        return None
    try:
        import fitz
        import numpy as np
        doc  = fitz.open(pdf_path)
        page = doc.load_page(page_num)
        mat  = fitz.Matrix(dpi / 72, dpi / 72)
        pix  = page.get_pixmap(matrix=mat, alpha=False)
        img  = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3
        )
        doc.close()
        return img
    except Exception as e:
        logger.warning("页面渲染失败 page=%d: %s", page_num, e)
        return None


# ── OCR 识别 ──────────────────────────────────────────────────────────────────

def ocr_page(img) -> str:
    """对 numpy 图像运行 PaddleOCR，返回合并后的文本字符串"""
    if not _PADDLE_AVAILABLE or img is None:
        return ""
    try:
        result = _get_ocr().ocr(img, cls=True)
        lines  = []
        for block in (result or []):
            for line in (block or []):
                if line and len(line) >= 2:
                    lines.append(line[1][0])
        return "\n".join(lines)
    except Exception as e:
        logger.warning("OCR 识别失败: %s", e)
        return ""


def analyze_layout(img) -> list[dict]:
    """
    用 PP-Structure 对页面做版面分析。
    返回区域列表 [{type, res}]，type ∈ {text, table, figure, title, ...}
    """
    global _struct_disabled, _struct_error_once
    if not _PADDLE_AVAILABLE or img is None or _struct_disabled:
        return []
    try:
        result = _get_struct()(img)
        return [{"type": r.get("type", "text"), "res": r.get("res", {})} for r in (result or [])]
    except Exception as e:
        _struct_disabled = True
        if not _struct_error_once:
            logger.warning("PP-Structure 分析失败，已禁用表格解析（后续不再尝试）: %s", e)
            _struct_error_once = True
        return []
