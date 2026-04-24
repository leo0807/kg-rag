from __future__ import annotations

import json
import logging
from typing import Callable

from ..ai.llm_service import get_llm_service
from .entity_filters import postprocess_entity_item

logger = logging.getLogger(__name__)


def _call_llm(prompt: str) -> str | None:
    try:
        return get_llm_service().chat([{"role": "user", "content": prompt}], temperature=0)
    except Exception as exc:
        logger.warning("LLM 调用失败: %s", exc)
        return None


def _parse_json(raw: str) -> list | dict | None:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("JSON 解析失败: %s | raw=%s", exc, raw[:200])
        return None


def _empty_entity_rows(sections: list[dict]) -> list[dict]:
    return [{"chunk_id": section["chunk_id"], "tools": [], "materials": [], "processes": [], "relations": []} for section in sections]


def _empty_constraint_rows(sections: list[dict]) -> list[dict]:
    return [{"chunk_id": section["chunk_id"], "constraints": []} for section in sections]


def extract_entities_from_sections(sections: list[dict], on_progress: Callable[[int, int], None] = None) -> list[dict]:
    results = []
    batch_size = 3
    total = len(sections)
    for index in range(0, total, batch_size):
        if on_progress:
            on_progress(index, total)
        results.extend(_extract_entity_batch(sections[index : index + batch_size]))
    if on_progress:
        on_progress(total, total)
    return results


def _extract_entity_batch(sections: list[dict]) -> list[dict]:
    combined = ""
    for section in sections:
        combined += (
            f"\n### [{section['chunk_id']}] {section.get('number', '')} {section.get('title', '')}\n"
            f"{section.get('content', '')[:500]}\n"
        )

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
- processes: 只保留“可执行的制造/装配/检验/测试动作”，必须是工艺动作短语（如“清洗”“力矩紧固”“压力测试”“点胶”“固化”）
- 不要把定义性描述、功能说明、状态词、连接关系、培训/职责/引用要求当成 process
- 以下这类通常应直接排除：完成、连接、设计、实现、作为依据、引用、人员培训、文件要求
- 若章节属于范围/引用文件/术语定义，除非出现明确工艺动作，否则 processes 留空
- 工具、材料名称必须是实体名，不要输出“无”或文档编号（如 CPS1000）
- relations 支持的类型：
    REQUIRES_TOOL  — Process 执行需要某 Tool
    USES_MATERIAL  — Process 执行使用某 Material
    ALTERNATIVE_TO — Material 可替代另一 Material
    COMPATIBLE_WITH — Material 与另一 Material 或 Tool 兼容使用
- chunk_id 必须逐字照抄输入中的章节 ID
- 若无关系，relations 为空数组
- 只输出 JSON，不要其他内容"""

    raw = _call_llm(prompt)
    if raw is None:
        return _empty_entity_rows(sections)

    data = _parse_json(raw)
    if not isinstance(data, list):
        logger.warning("实体提取返回格式异常，期望 list，得到 %s", type(data))
        return _empty_entity_rows(sections)

    chunk_ids = {section["chunk_id"] for section in sections}
    section_by_chunk_id = {section["chunk_id"]: section for section in sections}
    output = []
    for item in data:
        if item.get("chunk_id") not in chunk_ids:
            continue
        output.append(
            postprocess_entity_item(
                section_by_chunk_id[item["chunk_id"]],
                {
                    "chunk_id": item.get("chunk_id", ""),
                    "tools": item.get("tools", []),
                    "materials": item.get("materials", []),
                    "processes": item.get("processes", []),
                    "relations": item.get("relations", []),
                },
            )
        )

    returned = {item["chunk_id"] for item in output}
    for section in sections:
        if section["chunk_id"] not in returned:
            output.append({"chunk_id": section["chunk_id"], "tools": [], "materials": [], "processes": [], "relations": []})
    logger.info("实体提取完成，%d 个章节", len(output))
    return output


def extract_constraints_from_sections(sections: list[dict], on_progress: Callable[[int, int], None] = None) -> list[dict]:
    results = []
    batch_size = 5
    total = len(sections)
    for index in range(0, total, batch_size):
        if on_progress:
            on_progress(index, total)
        results.extend(_extract_constraint_batch(sections[index : index + batch_size]))
    if on_progress:
        on_progress(total, total)
    return results


def _extract_constraint_batch(sections: list[dict]) -> list[dict]:
    combined = ""
    for section in sections:
        combined += f"\n### [{section['chunk_id']}] {section.get('title','')}\n{section.get('content','')[:800]}\n"

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
        return _empty_constraint_rows(sections)

    data = _parse_json(raw)
    if not isinstance(data, list):
        return _empty_constraint_rows(sections)

    valid_types = {"torque", "tolerance", "temperature", "pressure", "clearance", "dimension"}
    chunk_ids = {section["chunk_id"] for section in sections}
    output = []
    for item in data:
        if item.get("chunk_id") not in chunk_ids:
            continue
        constraints = []
        for constraint in item.get("constraints", []):
            if not isinstance(constraint, dict):
                continue
            if constraint.get("type") not in valid_types:
                continue
            if not constraint.get("value") or not constraint.get("unit"):
                continue
            constraints.append(
                {
                    "type": constraint["type"],
                    "value": str(constraint["value"]),
                    "value_max": str(constraint.get("value_max", "") or ""),
                    "unit": constraint["unit"],
                    "description": constraint.get("description", ""),
                    "standard": constraint.get("standard", ""),
                }
            )
        output.append({"chunk_id": item["chunk_id"], "constraints": constraints})

    returned = {item["chunk_id"] for item in output}
    for section in sections:
        if section["chunk_id"] not in returned:
            output.append({"chunk_id": section["chunk_id"], "constraints": []})

    total_constraints = sum(len(item["constraints"]) for item in output)
    logger.info("约束提取完成，%d 个章节，共 %d 条约束", len(output), total_constraints)
    return output

