"""
src/services/entity_extractor.py
从章节文本中提取工具、材料、工序实体
"""
import json
import logging
import requests
from ..core.config import settings

logger = logging.getLogger(__name__)


def extract_entities_from_sections(sections: list[dict]) -> list[dict]:
    """
    批量从章节内容中提取实体。
    sections: [{"chunk_id", "title", "content"}]
    返回: [{"chunk_id", "tools": [...], "materials": [...], "processes": [...]}]
    """
    results = []
    # 每次最多处理 5 个章节，避免 token 过长
    batch_size = 5
    for i in range(0, len(sections), batch_size):
        batch = sections[i: i + batch_size]
        batch_results = _extract_batch(batch)
        results.extend(batch_results)
    return results


def _extract_batch(sections: list[dict]) -> list[dict]:
    """对一批章节调用 LLM 提取实体"""
    combined = ""
    for s in sections:
        combined += f"\n### [{s['chunk_id']}] {s.get('title','')}\n{s.get('content','')[:600]}\n"

    prompt = f"""你是航空制造工艺规范分析专家。请从以下规范章节中提取结构化实体信息。

{combined}

请以 JSON 数组格式输出，每个元素对应一个章节，格式如下：
[
  {{
    "chunk_id": "章节ID",
    "tools": ["工具名称1", "工具名称2"],
    "materials": ["材料名称1", "材料名称2"],
    "processes": ["工序名称1", "工序名称2"]
  }}
]

规则：
- tools: 工具、设备、仪器（如扳手、力矩扳手、液压泵、检测仪等）
- materials: 原材料、耗材、零件（如密封胶、润滑脂、O型圈、导线等）
- processes: 操作工序、步骤动词短语（如清洗、涂覆密封胶、力矩紧固、压力测试等）
- 只输出 JSON 数组，无其他内容
- 如果某章节无相关实体，对应数组为空列表"""

    try:
        res = requests.post(
            f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            timeout=60,
        )
        content = res.json()["choices"][0]["message"]["content"].strip()
        # 清理 markdown 代码块
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0]
        data = json.loads(content.strip())
        logger.info("实体提取完成，%d 个章节", len(data))
        return data
    except Exception as e:
        logger.warning("实体提取失败: %s", e)
        return [{"chunk_id": s["chunk_id"], "tools": [], "materials": [], "processes": []} for s in sections]
