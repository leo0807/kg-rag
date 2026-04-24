"""
src/services/formula_service.py
LaTeX 公式识别服务

主要能力：
- 基于 pix2tex（LatexOCR）识别图片中的数学/技术公式，输出 LaTeX 字符串
- 作为 VisionService task=formula 的本地备选方案
- 支持单图识别和批量识别

依赖（可选，未安装时自动降级到 VisionService）：
    pip install pix2tex[gui]
    # 或仅命令行版本：
    pip install pix2tex

用法示例：
    from .formula_service import recognize_formula
    result = recognize_formula("/path/to/image.png")
    # {"latex": "E = mc^2", "confidence": 0.92, "source": "pix2tex"}
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 可选依赖探测 ──────────────────────────────────────────────────────────────
_PIX2TEX_AVAILABLE = False
try:
    import pix2tex as _pix2tex_check  # noqa: F401
    _PIX2TEX_AVAILABLE = True
except ImportError:
    pass

# 懒初始化单例（模型较大，避免无谓加载）
_model_instance = None


def is_available() -> bool:
    """pix2tex 是否已安装且可用。"""
    return _PIX2TEX_AVAILABLE


def _get_model():
    """懒加载 pix2tex LatexOCR 模型单例。"""
    global _model_instance
    if _model_instance is None:
        from pix2tex.cli import LatexOCR
        logger.info("加载 pix2tex LatexOCR 模型...")
        _model_instance = LatexOCR()
        logger.info("pix2tex 模型加载完成")
    return _model_instance


# ── 图像预处理（提升识别精度）────────────────────────────────────────────────

def _preprocess_for_formula(image_path: str):
    """
    针对公式识别的图像预处理：
    - 转灰度
    - 自适应二值化（提升低对比度公式的识别率）
    - 添加白色边距（pix2tex 对边缘公式更准确）
    返回 PIL.Image，预处理失败则返回原图。
    """
    try:
        from PIL import Image, ImageOps, ImageFilter
        import numpy as np

        img = Image.open(image_path).convert("RGB")

        # 转灰度
        gray = img.convert("L")

        # 将灰度图转为 numpy 用于自适应处理
        arr = np.array(gray)

        # 自动判断背景色：若均值 < 128 则为深色背景，需要反色
        if arr.mean() < 128:
            gray = ImageOps.invert(gray)
            arr  = np.array(gray)

        # 简单二值化（Otsu 阈值）
        try:
            import cv2
            _, binary = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed = Image.fromarray(binary)
        except ImportError:
            # 无 OpenCV 时直接用灰度图
            processed = gray

        # 添加白色边距
        padded = ImageOps.expand(processed, border=20, fill=255)
        return padded.convert("RGB")

    except Exception as e:
        logger.debug("公式图像预处理失败（使用原图）: %s", e)
        from PIL import Image
        return Image.open(image_path).convert("RGB")


# ── 主识别函数 ─────────────────────────────────────────────────────────────────

def recognize_formula(image_path: str) -> dict[str, Any]:
    """
    识别图片中的数学/技术公式，返回 LaTeX 字符串。

    Args:
        image_path: 图片本地路径（PNG / JPG / BMP）

    Returns:
        {
            "latex":      "LaTeX 公式字符串",
            "description": "公式含义（pix2tex 不提供，留空供上层填充）",
            "source":     "pix2tex" | "vision_service" | "empty",
            "confidence": float (0~1，pix2tex 暂不提供置信度，固定为 1.0)
        }
    """
    empty = {
        "latex":       "",
        "description": "",
        "source":      "empty",
        "confidence":  0.0,
    }

    if not Path(image_path).exists():
        logger.warning("公式图片不存在: %s", image_path)
        return empty

    # ── 优先使用 pix2tex ──────────────────────────────────────────────────────
    if _PIX2TEX_AVAILABLE:
        try:
            model  = _get_model()
            img    = _preprocess_for_formula(image_path)
            latex  = model(img)
            latex  = (latex or "").strip()
            if latex:
                logger.info("pix2tex 识别完成: %.80s", latex)
                return {
                    "latex":       latex,
                    "description": "",
                    "source":      "pix2tex",
                    "confidence":  1.0,
                }
            logger.warning("pix2tex 返回空结果: %s", image_path)
        except Exception as e:
            logger.warning("pix2tex 识别失败，回退到 VisionService: %s", e)

    # ── 降级：VisionService task=formula ─────────────────────────────────────
    try:
        from .vision_service import get_vision_service
        result = get_vision_service().analyze_image(image_path, "formula")
        if result.get("latex"):
            return {
                "latex":       result["latex"],
                "description": result.get("description", ""),
                "source":      "vision_service",
                "confidence":  0.8,
            }
    except Exception as e:
        logger.warning("VisionService formula 识别也失败: %s", e)

    return empty


def recognize_formula_batch(
    image_paths: list[str],
) -> list[dict[str, Any]]:
    """
    批量识别公式，返回与输入等长的结果列表。
    每项：{"path": "...", "latex": "...", "source": "...", "confidence": float}
    """
    results = []
    for path in image_paths:
        r = recognize_formula(path)
        results.append({"path": path, **r})
    return results


# ── 辅助：判断图片是否可能包含公式 ───────────────────────────────────────────

def is_formula_image(image_path: str, min_aspect: float = 1.5) -> bool:
    """
    启发式判断一张图片是否可能包含数学公式（而非示意图）：
    - 宽高比 > 1.5（公式通常为横向长条）
    - 图片较小（纯公式区域一般不大）
    - 灰度均值高（白底黑字的公式）

    仅作为粗筛，不保证准确。
    """
    try:
        from PIL import Image
        import numpy as np
        img  = Image.open(image_path).convert("L")
        w, h = img.size
        aspect = w / max(h, 1)
        area   = w * h
        mean   = np.array(img).mean()
        return aspect > min_aspect and area < 300 * 300 and mean > 180
    except Exception:
        return False
