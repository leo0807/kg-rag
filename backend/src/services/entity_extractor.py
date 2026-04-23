from __future__ import annotations

"""
src/services/entity_extractor.py
从章节文本中提取：
  - 实体：Tool / Material / Process
  - 实体间关系：REQUIRES_TOOL / USES_MATERIAL / ALTERNATIVE_TO / COMPATIBLE_WITH
"""
import json
import logging
import re
from typing import Callable
from .llm_service import get_llm_service

logger = logging.getLogger(__name__)

_DOC_ID_RE = re.compile(r"^[A-Z]{2,}\d{3,}[A-Z0-9_-]*$")
_ENTITY_EMPTY_WORDS = {"无", "见", "详见", "无要求", "本规范", "本工艺规范"}
_PROCESS_SHORT_ALLOW = {
    "清洗", "清理", "检查", "检验", "测试", "试验", "涂胶", "点胶", "混胶", "混合",
    "定位", "夹紧", "固化", "切割", "打磨", "装配", "加工", "拒收",
}
_PROCESS_ACTION_HINTS = (
    "清洗", "清理", "检查", "检验", "测试", "试验", "紧固", "涂胶", "涂覆", "点胶", "混胶",
    "混合", "固化", "校准", "测量", "装配", "加工", "切割", "打磨",
    "修补", "封包", "封严", "定位", "夹紧", "密封", "验证", "拒收",
)
_PROCESS_EXACT_BLOCKLIST = {
    "完成", "连接", "设计", "实现", "相连", "装于", "位于", "用于", "引用",
    "获得", "规定", "记录", "控制", "分析", "确定", "编制", "作为依据",
    "作为文件", "入口接", "出口接", "检索",
}
_PROCESS_PREFIX_BLOCKLIST = (
    "实现", "完成", "连接", "引用", "作为", "入口接", "出口接", "装于", "位于",
    "确认", "查看", "处于", "停放",
)
_PROCESS_PHRASE_BLOCK_HINTS = ("状态", "区域", "待机", "关停", "已完成")
_PROCESS_CANONICAL_HINTS = (
    "完工验证测试", "完工测试", "涂胶密封检验", "验证试验", "手工修补",
    "自动涂胶", "机器人自动涂胶", "重做试件", "压力测试", "清理", "清洗",
    "检查", "检验", "测试", "试验", "点胶", "涂胶", "修补", "拒收",
)
_PROCESS_META_HINTS = (
    "人员", "培训", "规范", "手册", "要求", "引用", "依据", "文件",
    "职责", "范围", "定义",
)
_META_SECTION_HINTS = ("范围", "引用", "术语", "定义", "缩略语")


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


def _normalize_entity_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text.strip("，。；;：:、\"'`()[]【】<>《》")


def _looks_like_meta_section(section: dict) -> bool:
    title = _normalize_entity_text(section.get("title", ""))
    if any(hint in title for hint in _META_SECTION_HINTS):
        return True
    content = _normalize_entity_text(section.get("content", ""))[:80]
    if title and len(title) <= 12 and content.startswith(title):
        return True
    return False


def _keep_common_entity(name: str) -> bool:
    text = _normalize_entity_text(name)
    compact = text.replace(" ", "")
    if not compact or compact in _ENTITY_EMPTY_WORDS:
        return False
    if len(compact) <= 1:
        return False
    if _DOC_ID_RE.fullmatch(compact):
        return False
    return True


def _keep_process_name(name: str, section: dict) -> bool:
    text = _normalize_entity_text(name)
    compact = text.replace(" ", "")
    if not _keep_common_entity(text):
        return False
    if compact in _PROCESS_EXACT_BLOCKLIST:
        return False
    if any(compact.startswith(prefix) for prefix in _PROCESS_PREFIX_BLOCKLIST):
        return False
    if any(hint in compact for hint in _PROCESS_PHRASE_BLOCK_HINTS):
        return False
    if len(compact) <= 2 and compact not in _PROCESS_SHORT_ALLOW:
        return False

    has_action_hint = any(hint in compact for hint in _PROCESS_ACTION_HINTS)
    has_meta_hint = any(hint in compact for hint in _PROCESS_META_HINTS)

    if has_meta_hint and not has_action_hint:
        return False
    if _looks_like_meta_section(section) and not has_action_hint:
        return False
    return True


def _normalize_process_name(name: str) -> str:
    compact = _normalize_entity_text(name).replace(" ", "")
    if compact.startswith("机器人自动") and "涂胶" in compact:
        return "自动涂胶"
    for hint in _PROCESS_CANONICAL_HINTS:
        if hint in compact:
            return hint
    return compact


def _postprocess_entity_item(section: dict, item: dict) -> dict:
    tools = [
        _normalize_entity_text(t)
        for t in item.get("tools", [])
        if isinstance(t, str) and _keep_common_entity(t)
    ]
    materials = [
        _normalize_entity_text(m)
        for m in item.get("materials", [])
        if isinstance(m, str) and _keep_common_entity(m)
    ]
    processes = [
        _normalize_process_name(p)
        for p in item.get("processes", [])
        if isinstance(p, str) and _keep_process_name(p, section)
    ]

    allowed_processes = {p.replace(" ", "") for p in processes}
    relations = []
    for rel in item.get("relations", []):
        if not isinstance(rel, dict):
            continue
        if not rel.get("from_name") or not rel.get("to_name"):
            continue
        if rel.get("rel") not in {"REQUIRES_TOOL", "USES_MATERIAL", "ALTERNATIVE_TO", "COMPATIBLE_WITH"}:
            continue
        from_name = _normalize_entity_text(rel["from_name"])
        to_name = _normalize_entity_text(rel["to_name"])
        from_type = rel.get("from_type")
        to_type = rel.get("to_type")
        if from_type == "Process":
            from_name = _normalize_process_name(from_name)
        if to_type == "Process":
            to_name = _normalize_process_name(to_name)
        if from_type == "Process" and from_name.replace(" ", "") not in allowed_processes:
            continue
        if to_type == "Process" and to_name.replace(" ", "") not in allowed_processes:
            continue
        if from_type in {"Tool", "Material"} and not _keep_common_entity(from_name):
            continue
        if to_type in {"Tool", "Material"} and not _keep_common_entity(to_name):
            continue
        relations.append({
            "from_type": from_type,
            "from_name": from_name,
            "rel": rel.get("rel"),
            "to_type": to_type,
            "to_name": to_name,
        })

    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            key = value.replace(" ", "")
            if key in seen:
                continue
            seen.add(key)
            out.append(value)
        return out

    return {
        "chunk_id": section["chunk_id"],
        "tools": _dedupe(tools),
        "materials": _dedupe(materials),
        "processes": _dedupe(processes),
        "relations": relations,
    }


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
    batch_size = 3
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
        combined += (
            f"\n### [{s['chunk_id']}] {s.get('number', '')} {s.get('title', '')}\n"
            f"{s.get('content','')[:500]}\n"
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
        return [{"chunk_id": s["chunk_id"], "tools": [], "materials": [], "processes": [], "relations": []} for s in sections]

    data = _parse_json(raw)
    if not isinstance(data, list):
        logger.warning("实体提取返回格式异常，期望 list，得到 %s", type(data))
        return [{"chunk_id": s["chunk_id"], "tools": [], "materials": [], "processes": [], "relations": []} for s in sections]

    # 补充缺失字段
    chunk_ids = {s["chunk_id"] for s in sections}
    out = []
    section_by_chunk_id = {s["chunk_id"]: s for s in sections}
    for item in data:
        if item.get("chunk_id") not in chunk_ids:
            continue
        out.append(_postprocess_entity_item(
            section_by_chunk_id[item["chunk_id"]],
            {
                "chunk_id": item.get("chunk_id", ""),
                "tools": item.get("tools", []),
                "materials": item.get("materials", []),
                "processes": item.get("processes", []),
                "relations": item.get("relations", []),
            },
        ))
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
