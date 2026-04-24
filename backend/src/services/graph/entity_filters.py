from __future__ import annotations

import re

DOC_ID_RE = re.compile(r"^[A-Z]{2,}\d{3,}[A-Z0-9_-]*$")
ENTITY_EMPTY_WORDS = {"无", "见", "详见", "无要求", "本规范", "本工艺规范"}
PROCESS_SHORT_ALLOW = {
    "清洗", "清理", "检查", "检验", "测试", "试验", "涂胶", "点胶", "混胶", "混合",
    "定位", "夹紧", "固化", "切割", "打磨", "装配", "加工", "拒收",
}
PROCESS_ACTION_HINTS = (
    "清洗", "清理", "检查", "检验", "测试", "试验", "紧固", "涂胶", "涂覆", "点胶", "混胶",
    "混合", "固化", "校准", "测量", "装配", "加工", "切割", "打磨",
    "修补", "封包", "封严", "定位", "夹紧", "密封", "验证", "拒收",
)
PROCESS_EXACT_BLOCKLIST = {
    "完成", "连接", "设计", "实现", "相连", "装于", "位于", "用于", "引用",
    "获得", "规定", "记录", "控制", "分析", "确定", "编制", "作为依据",
    "作为文件", "入口接", "出口接", "检索",
}
PROCESS_PREFIX_BLOCKLIST = (
    "实现", "完成", "连接", "引用", "作为", "入口接", "出口接", "装于", "位于",
    "确认", "查看", "处于", "停放",
)
PROCESS_PHRASE_BLOCK_HINTS = ("状态", "区域", "待机", "关停", "已完成")
PROCESS_CANONICAL_HINTS = (
    "完工验证测试", "完工测试", "涂胶密封检验", "验证试验", "手工修补",
    "自动涂胶", "机器人自动涂胶", "重做试件", "压力测试", "清理", "清洗",
    "检查", "检验", "测试", "试验", "点胶", "涂胶", "修补", "拒收",
)
PROCESS_META_HINTS = (
    "人员", "培训", "规范", "手册", "要求", "引用", "依据", "文件",
    "职责", "范围", "定义",
)
META_SECTION_HINTS = ("范围", "引用", "术语", "定义", "缩略语")


def normalize_entity_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text.strip("，。；;：:、\"'`()[]【】<>《》")


def looks_like_meta_section(section: dict) -> bool:
    title = normalize_entity_text(section.get("title", ""))
    if any(hint in title for hint in META_SECTION_HINTS):
        return True
    content = normalize_entity_text(section.get("content", ""))[:80]
    if title and len(title) <= 12 and content.startswith(title):
        return True
    return False


def keep_common_entity(name: str) -> bool:
    text = normalize_entity_text(name)
    compact = text.replace(" ", "")
    if not compact or compact in ENTITY_EMPTY_WORDS:
        return False
    if len(compact) <= 1:
        return False
    if DOC_ID_RE.fullmatch(compact):
        return False
    return True


def keep_process_name(name: str, section: dict) -> bool:
    text = normalize_entity_text(name)
    compact = text.replace(" ", "")
    if not keep_common_entity(text):
        return False
    if compact in PROCESS_EXACT_BLOCKLIST:
        return False
    if any(compact.startswith(prefix) for prefix in PROCESS_PREFIX_BLOCKLIST):
        return False
    if any(hint in compact for hint in PROCESS_PHRASE_BLOCK_HINTS):
        return False
    if len(compact) <= 2 and compact not in PROCESS_SHORT_ALLOW:
        return False

    has_action_hint = any(hint in compact for hint in PROCESS_ACTION_HINTS)
    has_meta_hint = any(hint in compact for hint in PROCESS_META_HINTS)
    if has_meta_hint and not has_action_hint:
        return False
    if looks_like_meta_section(section) and not has_action_hint:
        return False
    return True


def normalize_process_name(name: str) -> str:
    compact = normalize_entity_text(name).replace(" ", "")
    if compact.startswith("机器人自动") and "涂胶" in compact:
        return "自动涂胶"
    for hint in PROCESS_CANONICAL_HINTS:
        if hint in compact:
            return hint
    return compact


def postprocess_entity_item(section: dict, item: dict) -> dict:
    tools = [
        normalize_entity_text(tool)
        for tool in item.get("tools", [])
        if isinstance(tool, str) and keep_common_entity(tool)
    ]
    materials = [
        normalize_entity_text(material)
        for material in item.get("materials", [])
        if isinstance(material, str) and keep_common_entity(material)
    ]
    processes = [
        normalize_process_name(process)
        for process in item.get("processes", [])
        if isinstance(process, str) and keep_process_name(process, section)
    ]

    allowed_processes = {process.replace(" ", "") for process in processes}
    relations = []
    for rel in item.get("relations", []):
        if not isinstance(rel, dict):
            continue
        if not rel.get("from_name") or not rel.get("to_name"):
            continue
        if rel.get("rel") not in {"REQUIRES_TOOL", "USES_MATERIAL", "ALTERNATIVE_TO", "COMPATIBLE_WITH"}:
            continue
        from_name = normalize_entity_text(rel["from_name"])
        to_name = normalize_entity_text(rel["to_name"])
        from_type = rel.get("from_type")
        to_type = rel.get("to_type")
        if from_type == "Process":
            from_name = normalize_process_name(from_name)
        if to_type == "Process":
            to_name = normalize_process_name(to_name)
        if from_type == "Process" and from_name.replace(" ", "") not in allowed_processes:
            continue
        if to_type == "Process" and to_name.replace(" ", "") not in allowed_processes:
            continue
        if from_type in {"Tool", "Material"} and not keep_common_entity(from_name):
            continue
        if to_type in {"Tool", "Material"} and not keep_common_entity(to_name):
            continue
        relations.append(
            {
                "from_type": from_type,
                "from_name": from_name,
                "rel": rel.get("rel"),
                "to_type": to_type,
                "to_name": to_name,
            }
        )

    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            key = value.replace(" ", "")
            if key in seen:
                continue
            seen.add(key)
            output.append(value)
        return output

    return {
        "chunk_id": section["chunk_id"],
        "tools": _dedupe(tools),
        "materials": _dedupe(materials),
        "processes": _dedupe(processes),
        "relations": relations,
    }

