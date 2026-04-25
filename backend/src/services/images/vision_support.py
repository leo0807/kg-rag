from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPTS: dict[str, str] = {
    "table": """你是一个航空工艺规范专家。请仔细分析图片中的表格，提取完整的行列数据。

要求：
- headers：表格第一行的列名列表（字符串数组，使用图中实际文字）
- rows：其余每行数据（二维字符串数组，行列顺序与原表一致，使用图中实际数据）
- caption：若表格有标题则填写，否则为空字符串

无论图中是否有表格，都必须只输出 JSON，不得复述问题、不得输出示例文字、不得输出任何解释。
- 若图中有表格：{"headers": ["实际列名1", "实际列名2"], "rows": [["实际值1", "实际值2"]], "caption": "实际标题或空字符串"}
- 若图中没有表格：{"headers": [], "rows": [], "caption": "", "note": "无表格"}""",
    "figure": """你是一个航空制造工艺规范专家。请仔细分析这张工艺示意图，理解其中的装配关系或工艺流程。

要求：
- description：对图片内容的详细中文描述（100字以内）
- relations：图中零件/组件之间的装配或连接关系（字符串数组，如 "A 装入 B"）
- steps：图中展示的操作步骤（字符串数组，顺序描述）
- tools：图中出现的工具名称（字符串数组）
- dimensions：图中标注的尺寸或规格（字符串数组）

只输出如下 JSON，不含任何额外文字：
{"description": "...", "relations": [...], "steps": [...], "tools": [...], "dimensions": [...]}""",
    "formula": """请识别图片中的数学公式或技术参数公式，转换为 LaTeX 格式。

要求：
- latex：完整的 LaTeX 公式字符串（不含 $$ 分隔符）
- description：公式的中文含义说明（30字以内）

只输出如下 JSON，不含任何额外文字：
{"latex": "...", "description": "..."}""",
}

EMPTY_RESULTS: dict[str, dict] = {
    "table": {"headers": [], "rows": [], "caption": ""},
    "figure": {"description": "", "relations": [], "steps": [], "tools": [], "dimensions": []},
    "formula": {"latex": "", "description": ""},
}


def load_image_b64(image_path: str) -> tuple[str, str]:
    ext = Path(image_path).suffix.lower().lstrip(".")
    media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
    with open(image_path, "rb") as file:
        b64 = base64.b64encode(file.read()).decode()
    return b64, media_type


def parse_json_response(content: str, task: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        logger.warning("VisionService JSON 解析失败，task=%s，内容预览: %.100s", task, content)
        return dict(EMPTY_RESULTS[task])
