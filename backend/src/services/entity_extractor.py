"""
src/services/entity_extractor.py
从章节文本中提取：
  - 实体：Tool / Material / Process
  - 实体间关系：REQUIRES_TOOL / USES_MATERIAL / ALTERNATIVE_TO / COMPATIBLE_WITH
"""
import json
import logging
from typing import Callable
from .llm_service import get_llm_service

logger = logging.getLogger(__name__)


def _call_llm(prompt: str) -> str | None:
    """统一的 LLM 调用，返回原始 content 字符串，失败返回 None"""
    try:
        return get_llm_service().chat(
            [{"role": "user", "content": prompt}],
            temperature=0,
        )
    except Exception as e:
        logger.warning("LLM 调用失败: %s", e)
        return None


def _parse_json(raw: str) -> list | dict | None:
    """从 LLM 响应中解析 JSON，自动去除 markdown 代码块"""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("JSON 解析失败: %s | raw=%s", e, raw[:200])
        return None


# ── 实体提取 ──────────────────────────────────────────────────────────────────

def extract_entities_from_sections(sections: list[dict], on_progress: Callable[[int, int], None] = None) -> list[dict]:
    """
    批量从章节内容中提取实体和实体间关系。
    sections: [{"chunk_id", "title", "content"}]
    返回: [{
        "chunk_id",
        "tools": [...], "materials": [...], "processes": [...],
        "relations": [{"from_type", "from_name", "rel", "to_type", "to_name"}]
    }]
    """
    results = []
    batch_size = 5
    total = len(sections)
    for i in range(0, total, batch_size):
        if on_progress:
            on_progress(i, total)
        batch = sections[i: i + batch_size]
        results.extend(_extract_entity_batch(batch))
    if on_progress:
        on_progress(total, total)
    return results


def _extract_entity_batch(sections: list[dict]) -> list[dict]:
    """对一批章节提取实体及实体间关系"""
    combined = ""
    for s in sections:
        combined += f"\n### [{s['chunk_id']}] {s.get('title','')}\n{s.get('content','')[:600]}\n"

    prompt = f"""你是航空制造工艺规范分析专家。请从以下规范章节中提取实体和实体间关系。

{combined}

请以 JSON 数组格式输出，每个元素对应一个章节：
[
  {{
    "chunk_id": "章节ID",
    "tools":     ["工具名称"],
    "materials": ["材料名称"],
    "processes": ["工序名称"],
    "relations": [
      {{"from_type": "Process", "from_name": "力矩紧固", "rel": "REQUIRES_TOOL",  "to_type": "Tool",     "to_name": "力矩扳手"}},
      {{"from_type": "Process", "from_name": "涂覆密封胶","rel": "USES_MATERIAL", "to_type": "Material", "to_name": "密封胶"}},
      {{"from_type": "Material","from_name": "密封胶B",   "rel": "ALTERNATIVE_TO","to_type": "Material", "to_name": "密封胶A"}},
      {{"from_type": "Material","from_name": "润滑脂A",   "rel": "COMPATIBLE_WITH","to_type":"Material", "to_name": "O型圈"}}
    ]
  }}
]

提取规则：
- tools:     工具/设备/仪器（扳手、液压泵、检测仪等）
- materials: 原材料/耗材/零件（密封胶、润滑脂、O型圈等）
- processes: 操作工序动词短语（清洗、力矩紧固、压力测试等）
- relations 支持的类型：
    REQUIRES_TOOL  — Process 执行需要某 Tool
    USES_MATERIAL  — Process 执行使用某 Material
    ALTERNATIVE_TO — Material 可替代另一 Material
    COMPATIBLE_WITH — Material 与另一 Material 或 Tool 兼容使用
- 若无关系，relations 为空数组
- 只输出 JSON，不要其他内容"""

    raw = _call_llm(prompt)
    if raw is None:
        return [{"chunk_id": s["chunk_id"], "tools": [], "materials": [], "processes": [], "relations": []} for s in sections]

    data = _parse_json(raw)
    if not isinstance(data, list):
        logger.warning("实体提取返回格式异常，期望 list，得到 %s", type(data))
        return [{"chunk_id": s["chunk_id"], "tools": [], "materials": [], "processes": [], "relations": []} for s in sections]

    # 补充缺失字段
    chunk_ids = {s["chunk_id"] for s in sections}
    out = []
    for item in data:
        if item.get("chunk_id") not in chunk_ids:
            continue
        out.append({
            "chunk_id":  item.get("chunk_id", ""),
            "tools":     [t for t in item.get("tools", [])     if t and isinstance(t, str)],
            "materials": [m for m in item.get("materials", []) if m and isinstance(m, str)],
            "processes": [p for p in item.get("processes", []) if p and isinstance(p, str)],
            "relations": [r for r in item.get("relations", [])
                          if isinstance(r, dict) and r.get("from_name") and r.get("to_name")
                          and r.get("rel") in {"REQUIRES_TOOL", "USES_MATERIAL", "ALTERNATIVE_TO", "COMPATIBLE_WITH"}],
        })
    # 补充未返回的 chunk
    returned = {item["chunk_id"] for item in out}
    for s in sections:
        if s["chunk_id"] not in returned:
            out.append({"chunk_id": s["chunk_id"], "tools": [], "materials": [], "processes": [], "relations": []})

    logger.info("实体提取完成，%d 个章节", len(out))
    return out


# ── 约束提取 ──────────────────────────────────────────────────────────────────

def extract_constraints_from_sections(sections: list[dict], on_progress: Callable[[int, int], None] = None) -> list[dict]:
    """
    从章节中提取工艺约束参数（力矩、公差、温度、压力等）。
    返回: [{"chunk_id", "constraints": [{"type","value","value_max","unit","description","standard"}]}]
    """
    results = []
    batch_size = 5
    total = len(sections)
    for i in range(0, total, batch_size):
        if on_progress:
            on_progress(i, total)
        batch = sections[i: i + batch_size]
        results.extend(_extract_constraint_batch(batch))
    if on_progress:
        on_progress(total, total)
    return results


def _extract_constraint_batch(sections: list[dict]) -> list[dict]:
    combined = ""
    for s in sections:
        combined += f"\n### [{s['chunk_id']}] {s.get('title','')}\n{s.get('content','')[:800]}\n"

    prompt = f"""你是航空制造工艺规范数据提取专家。请从以下章节中提取所有工艺约束参数。

{combined}

以 JSON 数组输出，每个章节一个元素：
[
  {{
    "chunk_id": "章节ID",
    "constraints": [
      {{
        "type":        "torque",
        "value":       "15",
        "value_max":   "",
        "unit":        "N·m",
        "description": "液压导管接头安装力矩",
        "standard":    "±10%"
      }},
      {{
        "type":        "temperature",
        "value":       "-55",
        "value_max":   "125",
        "unit":        "°C",
        "description": "工作温度范围",
        "standard":    ""
      }}
    ]
  }}
]

type 枚举值：
  torque（力矩）、tolerance（公差/配合）、temperature（温度）、
  pressure（压力）、clearance（间隙）、dimension（尺寸）

规则：
- value / value_max 均为纯数字字符串
- 无上限时 value_max 为空字符串
- standard 填写允许偏差（如 "±5%"、"H7/h6"），无则为空
- 若章节无约束参数，constraints 为空数组
- 只输出 JSON，不要其他内容"""

    raw = _call_llm(prompt)
    if raw is None:
        return [{"chunk_id": s["chunk_id"], "constraints": []} for s in sections]

    data = _parse_json(raw)
    if not isinstance(data, list):
        return [{"chunk_id": s["chunk_id"], "constraints": []} for s in sections]

    valid_types = {"torque", "tolerance", "temperature", "pressure", "clearance", "dimension"}
    chunk_ids = {s["chunk_id"] for s in sections}
    out = []
    for item in data:
        if item.get("chunk_id") not in chunk_ids:
            continue
        constraints = []
        for c in item.get("constraints", []):
            if not isinstance(c, dict):
                continue
            if c.get("type") not in valid_types:
                continue
            if not c.get("value") or not c.get("unit"):
                continue
            constraints.append({
                "type":        c["type"],
                "value":       str(c["value"]),
                "value_max":   str(c.get("value_max", "") or ""),
                "unit":        c["unit"],
                "description": c.get("description", ""),
                "standard":    c.get("standard", ""),
            })
        out.append({"chunk_id": item["chunk_id"], "constraints": constraints})

    returned = {item["chunk_id"] for item in out}
    for s in sections:
        if s["chunk_id"] not in returned:
            out.append({"chunk_id": s["chunk_id"], "constraints": []})

    total = sum(len(x["constraints"]) for x in out)
    logger.info("约束提取完成，%d 个章节，共 %d 条约束", len(out), total)
    return out
