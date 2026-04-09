"""
src/services/drawing_analyzer.py
工程图纸专项 VLM 分析服务

针对机械工程图纸（装配图、零件图、示意图）提取：
- 是否为工程图纸的判定
- 零件编号 / 件号
- 尺寸与公差标注（孔径、壁厚、表面粗糙度等）
- 装配关系描述
"""
import json
import logging
import requests
from pathlib import Path
from ..core.config import settings
from .image_analyzer import image_to_base64

logger = logging.getLogger(__name__)

# 判断为工程图纸所需的最低置信度（VLM 返回 is_drawing=True）
_DRAWING_ANNOTATION_MIN = 1  # 至少 1 条标注才视为有效图纸分析


def analyze_drawing(
    image_path: str,
    caption:    str = "",
    doc_id:     str = "",
) -> dict:
    """
    对单张图片做工程图纸专项分析。
    返回结构：
    {
        "is_drawing":         bool,
        "part_numbers":       ["P/N 12345", ...],
        "annotations": [
            {
                "type":      "tolerance|dimension|surface|other",
                "raw":       "φ12 +0.02/-0.01",
                "parameter": "孔径",
                "value":     "12",
                "value_max": "12.02",
                "value_min": "11.99",
                "unit":      "mm"
            }
        ],
        "assembly_relations": ["活塞杆安装于缸体内", ...],
        "summary":            "液压缸装配图，标注孔径公差..."
    }
    """
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

    try:
        res = requests.post(
            f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model": settings.VLM_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            },
            timeout=90,
        )
        content = res.json()["choices"][0]["message"]["content"].strip()
        # 清理 markdown 代码块包裹
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
        logger.info(
            "图纸分析完成 %s: is_drawing=%s annotations=%d",
            image_path, result.get("is_drawing"), len(result.get("annotations", [])),
        )
        return result
    except Exception as e:
        logger.warning("图纸分析失败 %s: %s", image_path, e)
        return {
            "is_drawing":         False,
            "part_numbers":       [],
            "annotations":        [],
            "assembly_relations": [],
            "summary":            caption or "",
        }


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
