"""
规范结构分析器 — 从 Neo4j 中提取 CPS 规范的章节模式，构建结构模板。
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# ── 内置默认模板 ────────────────────────────────────────────────────────────

_DEFAULT_SECTIONS = [
    {"number": "1", "title": "范围",       "required": True,  "min_words": 50},
    {"number": "2", "title": "引用文件",   "required": True,  "min_words": 30},
    {"number": "3", "title": "术语和定义", "required": True,  "min_words": 30},
    {"number": "4", "title": "材料",       "required": False, "min_words": 50},
    {"number": "5", "title": "设备",       "required": False, "min_words": 50},
    {"number": "6", "title": "技术要求",   "required": True,  "min_words": 100},
    {"number": "7", "title": "工艺规程",   "required": True,  "min_words": 150},
    {"number": "8", "title": "检验与试验", "required": True,  "min_words": 80},
    {"number": "9", "title": "标识与记录", "required": False, "min_words": 30},
]

DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "sealing_general",
        "name": "通用密封类规范模板",
        "applicable_to": ["密封", "粘接", "密封剂"],
        "structure": {
            "sections": _DEFAULT_SECTIONS,
            "common_patterns": {
                "material_format": "牌号/规格 + 标准编号",
                "param_format": "数值 ± 容差 单位",
            },
        },
        "sample_doc_ids": [],
    },
    {
        "template_id": "composite_repair",
        "name": "复合材料修复规范模板",
        "applicable_to": ["复合材料", "修复", "碳纤维"],
        "structure": {
            "sections": _DEFAULT_SECTIONS,
            "common_patterns": {
                "temp_format": "温度范围 ℃，保温时间 min",
                "pressure_format": "固化压力 MPa",
            },
        },
        "sample_doc_ids": [],
    },
    {
        "template_id": "fastener_general",
        "name": "紧固件安装规范模板",
        "applicable_to": ["紧固件", "螺栓", "铆钉"],
        "structure": {
            "sections": _DEFAULT_SECTIONS,
            "common_patterns": {
                "torque_format": "扭矩值 N·m ± 容差",
            },
        },
        "sample_doc_ids": [],
    },
    {
        "template_id": "surface_treatment",
        "name": "表面处理规范模板",
        "applicable_to": ["表面处理", "涂层", "阳极化", "镀层"],
        "structure": {
            "sections": _DEFAULT_SECTIONS,
            "common_patterns": {
                "thickness_format": "膜厚 μm，范围 min~max",
            },
        },
        "sample_doc_ids": [],
    },
]


def get_default_templates() -> list[dict[str, Any]]:
    """返回内置默认模板列表。"""
    return DEFAULT_TEMPLATES


def _normalize_title(title: str) -> str:
    """标准化章节标题：去除编号前缀，统一到关键词。"""
    title = re.sub(r"^\d+[\.\s]+", "", title.strip())
    return title[:50]


def _extract_section_numbers(sections: list[dict]) -> list[str]:
    nums = []
    for s in sections:
        title = s.get("title", "")
        m = re.match(r"^(\d+(?:\.\d+)?)", title)
        if m:
            nums.append(m.group(1))
    return nums


def analyze_doc_structure(driver, doc_id: str) -> dict[str, Any]:
    """
    从 Neo4j 查询单份文档的章节结构。
    返回 {"doc_id": ..., "sections": [{"number": ..., "title": ...}]}
    """
    query = """
    MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
    RETURN s.section_number AS number, s.title AS title, s.content AS content
    ORDER BY s.section_number
    """
    try:
        with driver.session() as sess:
            result = sess.run(query, doc_id=doc_id)
            sections = [
                {
                    "number": r["number"] or "",
                    "title":  _normalize_title(r["title"] or ""),
                    "word_count": len((r["content"] or "").split()),
                }
                for r in result
                if r["title"]
            ]
        return {"doc_id": doc_id, "sections": sections}
    except Exception as e:
        logger.warning("analyze_doc_structure %s failed: %s", doc_id, e)
        return {"doc_id": doc_id, "sections": []}


def extract_template_from_docs(
    driver,
    doc_ids: list[str],
    template_id: str,
    name: str,
    applicable_to: list[str],
) -> dict[str, Any]:
    """
    从指定文档列表中提取共同章节结构，构造模板 dict。
    """
    all_structures: list[dict] = []
    for doc_id in doc_ids[:20]:  # cap at 20 samples
        struct = analyze_doc_structure(driver, doc_id)
        if struct["sections"]:
            all_structures.append(struct)

    if not all_structures:
        # fallback to default
        base = next((t for t in DEFAULT_TEMPLATES if t["template_id"] == "sealing_general"), DEFAULT_TEMPLATES[0])
        return {**base, "template_id": template_id, "name": name, "applicable_to": applicable_to, "sample_doc_ids": doc_ids}

    # Count title frequency across docs
    title_counter: Counter = Counter()
    title_words: dict[str, list[int]] = defaultdict(list)
    for struct in all_structures:
        for sec in struct["sections"]:
            t = sec["title"]
            title_counter[t] += 1
            title_words[t].append(sec.get("word_count", 0))

    total = len(all_structures)
    sections = []
    for title, count in title_counter.most_common(15):
        freq = count / total
        if freq < 0.3:
            continue
        avg_words = int(sum(title_words[title]) / len(title_words[title]))
        sections.append({
            "title":     title,
            "required":  freq >= 0.8,
            "frequency": round(freq, 2),
            "min_words": max(30, avg_words // 2),
        })

    return {
        "template_id":   template_id,
        "name":          name,
        "applicable_to": applicable_to,
        "structure": {
            "sections": sections,
            "common_patterns": {},
        },
        "sample_doc_ids": doc_ids[:5],
    }
