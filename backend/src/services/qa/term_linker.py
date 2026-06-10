"""
术语自动链接 — 提取答案中的 CPS 编号与术语，返回链接注释
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


_CPS_RE = re.compile(r'\b(CPS\s*\d{4,6}(?:[A-Z]\d*)?)\b', re.IGNORECASE)

# 常用术语词典（扩展方向：从 DB 动态加载）
_TERM_DICT: dict[str, str] = {
    "密封剂": "用于密封结构缝隙、防止液体或气体渗漏的化学材料",
    "底漆": "涂装工艺的第一道涂层，用于提高粘附力和防腐蚀",
    "固化": "材料在一定温度/时间条件下完成交联反应的过程",
    "NDT": "非破坏性检测（Non-Destructive Testing）的缩写",
    "AOG": "飞机停场检修（Aircraft on Ground）",
    "MRO": "维修、修理与大修（Maintenance, Repair, Overhaul）",
    "FAR": "适航法规（Federal Aviation Regulations）",
    "CCAR": "中国民用航空规章（China Civil Aviation Regulations）",
    "搭铁": "飞机结构的电气接地连接",
    "表面处理": "通过化学或物理方法改变材料表面性质，以提高粘附力或防腐性能",
    "铆接": "用铆钉连接金属零部件的工艺方法",
    "阳极氧化": "铝合金表面的电化学氧化处理，增强耐腐蚀性",
    "热处理": "通过加热和冷却改变材料微观结构的工艺",
    "复合材料": "由两种或多种材料组合而成的工程材料",
    "蒙皮": "飞机外表面的薄板结构件",
}


@dataclass
class LinkAnnotation:
    start: int
    end: int
    text: str
    kind: str          # "cps" | "term"
    href: str          # relative URL
    tooltip: str


def extract_links(text: str) -> list[LinkAnnotation]:
    """提取文本中的 CPS 编号和术语链接。"""
    results: list[LinkAnnotation] = []
    seen_spans: list[tuple[int, int]] = []

    def _overlap(s: int, e: int) -> bool:
        return any(s < e2 and e > s2 for s2, e2 in seen_spans)

    # CPS 编号
    for m in _CPS_RE.finditer(text):
        doc_id = re.sub(r'\s+', '', m.group()).upper()
        results.append(LinkAnnotation(
            start=m.start(), end=m.end(),
            text=m.group(), kind="cps",
            href=f"/wiki/{doc_id}",
            tooltip=f"查看 {doc_id} 规范详情",
        ))
        seen_spans.append((m.start(), m.end()))

    # 术语
    for term, definition in _TERM_DICT.items():
        idx = 0
        while True:
            pos = text.find(term, idx)
            if pos < 0:
                break
            end = pos + len(term)
            if not _overlap(pos, end):
                results.append(LinkAnnotation(
                    start=pos, end=end,
                    text=term, kind="term",
                    href=f"/wiki/term/{term}",
                    tooltip=definition,
                ))
                seen_spans.append((pos, end))
            idx = pos + 1

    results.sort(key=lambda a: a.start)
    return results


def annotate_html(text: str) -> str:
    """将纯文本中的链接替换为带 data- 属性的 <span> 标签（前端渲染用）。"""
    links = extract_links(text)
    if not links:
        return text

    parts: list[str] = []
    cursor = 0
    for lnk in links:
        parts.append(text[cursor: lnk.start])
        cls = "cps-link" if lnk.kind == "cps" else "term-link"
        parts.append(
            f'<span class="{cls}" data-href="{lnk.href}" data-tooltip="{lnk.tooltip}">'
            f'{lnk.text}</span>'
        )
        cursor = lnk.end
    parts.append(text[cursor:])
    return "".join(parts)
