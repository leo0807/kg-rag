"""
src/services/counterfactual_intent.py
反事实问题意图解析模块

从反事实假设问题中提取：被去掉的实体类型/名称、受影响主体、目标要求。
"""
import json
import logging
import re
import requests
from ..core.config import settings

logger = logging.getLogger(__name__)

# ── 类型标签映射 ──────────────────────────────────────────────
_TYPE_CN = {
    "Process":    "工艺/工序",
    "Tool":       "工具",
    "Material":   "材料",
    "Constraint": "约束条件",
}

# ── 关系标签映射 ──────────────────────────────────────────────
_REL_CN = {
    "INVOLVES_PROCESS": "包含工序",
    "REQUIRES_TOOL":    "需要工具",
    "USES_MATERIAL":    "使用材料",
}


def _call_llm(prompt: str, timeout: int = 30) -> str:
    """调用 LLM（复用 settings 配置）"""
    res = requests.post(
        f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.LLM_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "model":    settings.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream":   False,
        },
        timeout=timeout,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def parse_counterfactual_intent(question: str) -> dict:
    """
    用 LLM 解析反事实问题中的关键实体。
    返回:
        removed_type  — Process | Tool | Material | unknown
        removed_name  — 被去掉的实体名称
        subject       — 受影响的零件/产品
        requirement   — 需要满足的要求/标准
    """
    prompt = f"""从以下反事实假设问题中提取关键信息，返回 JSON（只输出 JSON，不要有其他文字）。

问题：{question}

返回格式：
{{
  "removed_type": "Process 或 Tool 或 Material 或 unknown",
  "removed_name": "被去掉/省略/移除的具体名称（字符串）",
  "subject": "受影响的零件或产品（若问题中未提及则为空字符串）",
  "requirement": "需要满足的技术要求或标准（若未提及则为空字符串）"
}}

示例：
Q: "如果去掉热处理工序，铝合金蒙皮还能满足强度要求吗？"
A: {{"removed_type":"Process","removed_name":"热处理","subject":"铝合金蒙皮","requirement":"强度要求"}}

Q: "省略打孔前脱脂步骤，铆钉连接处是否仍满足密封标准？"
A: {{"removed_type":"Process","removed_name":"脱脂","subject":"铆钉连接处","requirement":"密封标准"}}

Q: "不用扭矩扳手，螺栓装配能否满足力矩要求？"
A: {{"removed_type":"Tool","removed_name":"扭矩扳手","subject":"螺栓装配","requirement":"力矩要求"}}

Q: "如果用普通铝合金代替钛合金，零件还能符合强度标准吗？"
A: {{"removed_type":"Material","removed_name":"钛合金","subject":"零件","requirement":"强度标准"}}"""

    try:
        raw   = _call_llm(prompt)
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning("反事实意图解析失败: %s", e)

    return _extract_intent_by_keywords(question)


def _extract_intent_by_keywords(question: str) -> dict:
    """LLM 解析失败时的关键词降级方案"""
    removed_name = ""
    removed_type = "unknown"

    patterns = [
        r"(?:去掉|省略|移除|不用|取消|跳过)[了的]?([^，。,\s]{2,10}?)(?:工序|步骤|处理|工具|材料)",
        r"(?:如果|假设|假如)(?:没有|不[使用做进行])[了的]?([^，。,\s]{2,10})",
    ]
    for p in patterns:
        m = re.search(p, question)
        if m:
            removed_name = m.group(1)
            break

    return {
        "removed_type": removed_type,
        "removed_name": removed_name,
        "subject":      "",
        "requirement":  "",
    }


# 导出供 counterfactual.py 使用
__all__ = ["_TYPE_CN", "_REL_CN", "_call_llm", "parse_counterfactual_intent", "_extract_intent_by_keywords"]
