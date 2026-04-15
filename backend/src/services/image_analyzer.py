"""
src/services/image_analyzer.py
多模态图片理解服务

使用视觉语言模型（VLM）分析工艺规范中的图片：
- 识别图中的工具、零件、工序步骤
- 提取尺寸标注、技术参数
- 生成结构化描述，写入知识图谱
"""
import logging
import base64
from pathlib import Path
from ..core.config import settings
from .llm_service import get_llm_service

logger = logging.getLogger(__name__)


def image_to_base64(image_path: str) -> str:
    """将图片转为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image(
    image_path: str,
    caption:    str = "",
    doc_id:     str = "",
    context:    str = "",
) -> dict:
    """
    使用 VLM 分析图片
    返回结构化描述：
    {
        "description": "图片的详细描述",
        "tools":       ["工具1", "工具2"],
        "steps":       ["步骤1", "步骤2"],
        "dimensions":  ["尺寸标注"],
        "keywords":    ["关键词"],
    }
    """
    ext        = Path(image_path).suffix.lower().lstrip(".")
    media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
    image_b64  = image_to_base64(image_path)

    prompt = f"""你是一个航空制造工艺规范专家。请分析这张工艺图片，提取以下信息：

图片来源：{doc_id}
图片说明：{caption or "无"}
{f"相关章节内容：{context[:200]}" if context else ""}

请用JSON格式回答，包含以下字段：
- description: 图片的详细中文描述（100字以内）
- tools: 图中出现的工具列表（数组）
- steps: 图中展示的操作步骤（数组）
- dimensions: 图中的尺寸或规格标注（数组）
- keywords: 关键技术词汇（数组，5个以内）

只输出JSON，不要其他内容。"""

    try:
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }]
        content = get_llm_service().chat(messages, model=settings.VLM_MODEL, timeout=60)

        # 清理 JSON 格式
        import json
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
        logger.info("图片分析完成 %s: %s", image_path, result.get("description", "")[:50])
        return result

    except Exception as e:
        logger.warning("图片分析失败 %s: %s", image_path, e)
        return {
            "description": caption or "工艺图片",
            "tools":       [],
            "steps":       [],
            "dimensions":  [],
            "keywords":    [],
        }


def analyze_images_batch(
    images:   list[dict],
    max_count: int = 20,
) -> list[dict]:
    """
    批量分析图片
    images: [{"image_id": ..., "path": ..., "caption": ..., "doc_id": ...}]
    """
    results = []
    for img in images[:max_count]:
        analysis = analyze_image(
            image_path = img["path"],
            caption    = img.get("caption", ""),
            doc_id     = img.get("doc_id", ""),
        )
        results.append({
            **img,
            "analysis": analysis,
        })
    return results


# ── VisionService 智能路由 ─────────────────────────────────────────────────────

def analyze_image_smart(
    image_path: str,
    caption:    str = "",
    doc_id:     str = "",
) -> dict:
    """
    智能图片分析：自动检测任务类型，委托 VisionService 处理。

    路由规则：
    - 图片通过 formula_service.is_formula_image() 判定为公式 → task=formula
    - 否则 → task=figure

    返回结构与 analyze_image() 保持一致，便于下游 write_images_to_graph 无感切换：
    {
        "description": str,
        "tools":       list[str],
        "steps":       list[str],
        "dimensions":  list[str],
        "keywords":    list[str],
        "task":        "figure" | "formula",
        "relations":   list[str],   # figure 专有
        "latex":       str,         # formula 专有
    }
    """
    from pathlib import Path as _Path

    empty = {
        "description": caption or "工艺图片",
        "tools": [], "steps": [], "dimensions": [],
        "keywords": [], "task": "figure", "relations": [], "latex": "",
    }

    if not _Path(image_path).exists():
        logger.warning("图片不存在，跳过分析: %s", image_path)
        return empty

    # ── 判断任务类型 ──────────────────────────────────────────────────────────
    task = "figure"
    try:
        from .formula_service import is_formula_image
        if is_formula_image(image_path):
            task = "formula"
            logger.debug("图片识别为公式: %s", image_path)
    except Exception:
        pass

    # ── 公式路径 ──────────────────────────────────────────────────────────────
    if task == "formula":
        try:
            from .formula_service import recognize_formula
            result = recognize_formula(image_path)
            latex  = result.get("latex", "")
            desc   = result.get("description") or (f"公式: {latex}" if latex else caption or "公式图片")
            return {
                "description": desc,
                "tools":       [],
                "steps":       [],
                "dimensions":  [],
                "keywords":    [latex] if latex else [],
                "task":        "formula",
                "relations":   [],
                "latex":       latex,
            }
        except Exception as e:
            logger.warning("公式识别失败，降级为 figure: %s", e)
            task = "figure"

    # ── 示意图路径 ────────────────────────────────────────────────────────────
    try:
        from .vision_service import get_vision_service
        vs_result = get_vision_service().analyze_image(image_path, "figure")
        return {
            "description": vs_result.get("description") or caption or "工艺图片",
            "tools":       vs_result.get("tools", []),
            "steps":       vs_result.get("steps", []),
            "dimensions":  vs_result.get("dimensions", []),
            "keywords":    vs_result.get("relations", [])[:5],
            "task":        "figure",
            "relations":   vs_result.get("relations", []),
            "latex":       "",
        }
    except Exception as e:
        logger.warning("VisionService figure 分析失败，降级为旧接口: %s", e)

    # ── 最终降级：旧 LLM 直接调用 ─────────────────────────────────────────────
    legacy = analyze_image(image_path, caption, doc_id)
    return {**legacy, "task": "figure", "relations": [], "latex": ""}