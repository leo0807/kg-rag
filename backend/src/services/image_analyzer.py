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
    import requests

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
        res = requests.post(
            f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model": settings.VLM_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{image_b64}"
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            },
            timeout=60,
        )

        content = res.json()["choices"][0]["message"]["content"]

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