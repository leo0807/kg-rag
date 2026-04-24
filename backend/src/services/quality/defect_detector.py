"""
视觉质量检测（Visual QC AI）— 基于 YOLOv11/RT-DETR 的工件缺陷检测

依赖（可选，未安装时自动降级）:
    pip install ultralytics>=8.2.0

支持缺陷类型: 划痕(scratch)、裂纹(crack)、孔位偏差(hole_deviation)、
              凹坑(dent)、氧化(oxidation)、焊缝缺陷(weld_defect)
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 依赖探测 ──────────────────────────────────────────────────────────────────
_YOLO_AVAILABLE = False
try:
    import ultralytics as _ul  # noqa: F401
    _YOLO_AVAILABLE = True
except ImportError:
    pass

# 预定义缺陷类名 → 中文映射
DEFECT_LABELS: dict[str, str] = {
    "scratch":       "划痕",
    "crack":         "裂纹",
    "hole_deviation":"孔位偏差",
    "dent":          "凹坑",
    "oxidation":     "氧化",
    "weld_defect":   "焊缝缺陷",
    "burr":          "毛刺",
    "delamination":  "分层",
}

# 置信度阈值
_CONF_THRESHOLD = 0.35

# 懒加载模型单例
_model = None
_model_path: Optional[str] = None


def is_available() -> bool:
    return _YOLO_AVAILABLE


def set_model_path(path: str):
    """配置自定义 YOLO 模型权重路径（须在首次调用 detect 前设置）"""
    global _model_path
    _model_path = path


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        # 优先使用自定义权重，否则用 YOLOv11n（轻量）作为 demo 占位
        weights = _model_path or "yolo11n.pt"
        _model = YOLO(weights)
        logger.info("YOLO 模型已加载: %s", weights)
    return _model


# ── 缺陷检测 ──────────────────────────────────────────────────────────────────

def detect_defects(image_path: str) -> list[dict]:
    """
    对工件图片运行缺陷检测。

    返回:
        list of {
            defect_type: str,   # 英文类名
            label:       str,   # 中文标签
            confidence:  float,
            bbox:        [x1, y1, x2, y2],
        }
    """
    if not _YOLO_AVAILABLE:
        return []
    try:
        model = _get_model()
        results = model(image_path, conf=_CONF_THRESHOLD, verbose=False)
        defects = []
        for result in results:
            for box in result.boxes:
                cls_id  = int(box.cls[0])
                cls_name = result.names.get(cls_id, "unknown")
                conf    = float(box.conf[0])
                xyxy    = [round(v, 1) for v in box.xyxy[0].tolist()]
                defects.append({
                    "defect_type": cls_name,
                    "label":       DEFECT_LABELS.get(cls_name, cls_name),
                    "confidence":  round(conf, 3),
                    "bbox":        xyxy,
                })
        return defects
    except Exception as e:
        logger.warning("缺陷检测失败 path=%s: %s", image_path, e)
        return []


# ── VLM 回退（无 YOLO 权重时）────────────────────────────────────────────────

def detect_defects_vlm(image_path: str, doc_id: str = "") -> list[dict]:
    """
    使用 VLM（视觉语言模型）进行缺陷识别，作为 YOLO 的 fallback。
    返回与 detect_defects 相同格式。
    """
    import base64, json as _json
    from ..ai.llm import get_client, get_model

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = Path(image_path).suffix.lstrip(".").lower() or "jpeg"
        mime = f"image/{ext}"

        prompt = (
            "请检查这张工件图片，识别所有可见的质量缺陷。\n"
            "对每个缺陷，返回 JSON 数组，每项包含:\n"
            '{"defect_type": "scratch|crack|hole_deviation|dent|oxidation|weld_defect|burr|none", '
            '"label": "中文标签", "confidence": 0.0-1.0, "description": "描述"}\n'
            "若无缺陷，返回空数组 []。只返回 JSON，不加其他文字。"
        )
        client = get_client()
        resp = client.chat.completions.create(
            model=get_model(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=512,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content or "[]"
        # 提取 JSON 数组
        import re
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        items = _json.loads(m.group(0)) if m else []
        return [
            {
                "defect_type": it.get("defect_type", "unknown"),
                "label":       it.get("label", it.get("defect_type", "")),
                "confidence":  float(it.get("confidence", 0.5)),
                "bbox":        [],
                "description": it.get("description", ""),
            }
            for it in items
            if it.get("defect_type") not in ("none", "", None)
        ]
    except Exception as e:
        logger.warning("VLM 缺陷检测失败: %s", e)
        return []
