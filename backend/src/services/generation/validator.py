"""
规范草稿自检校验引擎 — 结构、引用、数值、术语一致性检查。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    severity:    str          # critical | major | minor
    section:     str
    description: str
    suggestion:  str = ""


@dataclass
class ValidationReport:
    overall_score:         float
    issues:                list[Issue] = field(default_factory=list)
    suggestions:           list[str]   = field(default_factory=list)
    requires_human_review: bool        = False

    def to_dict(self) -> dict:
        return {
            "overall_score":         self.overall_score,
            "requires_human_review": self.requires_human_review,
            "issues": [
                {
                    "severity":    i.severity,
                    "section":     i.section,
                    "description": i.description,
                    "suggestion":  i.suggestion,
                }
                for i in self.issues
            ],
            "suggestions": self.suggestions,
        }


# 必须出现的章节编号
_REQUIRED_SECTIONS = {"1", "2", "3", "6", "7", "8"}

# 数值带单位的正则（如 120±5℃，≥2.5 MPa）
_NUM_UNIT_RE = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*[±+\-]\s*\d+(?:\.\d+)?)?\s*"
    r"(℃|°C|MPa|kPa|N·m|N/mm²|mm|μm|min|h|s|%|kg|g|L|mL)\b"
)
# 疑似无单位数值
_BARE_NUM_RE = re.compile(r"\b(\d{2,}(?:\.\d+)?)\b")

# 模糊词
_VAGUE_WORDS = ["大约", "约", "左右", "参考", "适当", "适量", "若干", "合适"]

# CPS 编号格式
_CPS_REF_RE = re.compile(r"\bCPS\s*\d{4}\b", re.IGNORECASE)


class SpecValidator:

    def check_structure(self, sections: dict[str, str]) -> list[Issue]:
        issues: list[Issue] = []
        present = set(sections.keys())

        for req in _REQUIRED_SECTIONS:
            if req not in present or not (sections.get(req) or "").strip():
                issues.append(Issue(
                    severity="critical",
                    section=req,
                    description=f"必需章节 §{req} 缺失或为空",
                    suggestion=f"补充 §{req} 章节内容",
                ))

        for num, content in sections.items():
            if len((content or "").split()) < 20:
                issues.append(Issue(
                    severity="major",
                    section=num,
                    description=f"§{num} 内容过短（不足20词）",
                    suggestion="扩充该章节内容",
                ))

        return issues

    def check_references(self, sections: dict[str, str], doc_ids: list[str]) -> list[Issue]:
        issues: list[Issue] = []
        sec2 = sections.get("2", "")

        for doc_id in (doc_ids or []):
            cps_num = re.sub(r"[^0-9]", "", doc_id)
            if cps_num and f"CPS{cps_num}" not in sec2 and doc_id not in sec2:
                issues.append(Issue(
                    severity="minor",
                    section="2",
                    description=f"参考文档 {doc_id} 未在引用文件章节中出现",
                    suggestion=f"在 §2 中添加对 {doc_id} 的引用",
                ))

        # 检查正文中的 CPS 引用格式
        for num, content in sections.items():
            if num == "2":
                continue
            raw_refs = re.findall(r"CPS\s*\d+", content, re.IGNORECASE)
            for ref in raw_refs:
                normalized = re.sub(r"\s+", "", ref).upper()
                if not re.match(r"CPS\d{4}", normalized):
                    issues.append(Issue(
                        severity="minor",
                        section=num,
                        description=f"引用编号格式疑似不规范：{ref}",
                        suggestion="规范编号格式应为 CPSXXXX（4位数字）",
                    ))

        return issues

    def check_numerical(self, sections: dict[str, str]) -> list[Issue]:
        issues: list[Issue] = []
        high_priority = {"6", "7", "8"}

        for num in high_priority:
            content = sections.get(num, "")
            if not content:
                continue

            # 寻找明显无单位的独立数字
            bare = _BARE_NUM_RE.findall(content)
            with_unit = set(_NUM_UNIT_RE.findall(content))
            suspicious = [n for n in bare if n not in content and len(with_unit) == 0]

            if bare and not with_unit and len(bare) > 2:
                issues.append(Issue(
                    severity="major",
                    section=num,
                    description=f"§{num} 存在数值但未见单位标注",
                    suggestion="所有数值参数（温度/压力/时间等）须标注单位",
                ))

            # 检查模糊词
            for word in _VAGUE_WORDS:
                if word in content:
                    issues.append(Issue(
                        severity="major",
                        section=num,
                        description=f'§{num} 出现模糊词语："{word}"',
                        suggestion=f'将"{word}"替换为明确数值或范围',
                    ))
                    break

        return issues

    def check_terminology(self, sections: dict[str, str]) -> list[Issue]:
        issues: list[Issue] = []
        terms_sec = sections.get("3", "")

        defined_terms: list[str] = []
        for line in terms_sec.split("\n"):
            m = re.match(r"3\.\d+\s+([^\n（(]+)", line)
            if m:
                defined_terms.append(m.group(1).strip())

        if not defined_terms:
            return issues

        # 检查非 §3 章节是否使用了未定义的专业词（简化版：仅检查长词）
        full_text = " ".join(
            v for k, v in sections.items() if k not in ("3",) and v
        )
        # 只做基本提示，不做深度NLP
        if len(defined_terms) < 3:
            issues.append(Issue(
                severity="minor",
                section="3",
                description="术语和定义章节定义词条较少（不足3条）",
                suggestion="补充常用专业术语定义",
            ))

        return issues

    def validate_full(
        self,
        sections: dict[str, str],
        inputs: dict,
        doc_ids: list[str],
    ) -> dict:
        all_issues: list[Issue] = []
        all_issues += self.check_structure(sections)
        all_issues += self.check_references(sections, doc_ids)
        all_issues += self.check_numerical(sections)
        all_issues += self.check_terminology(sections)

        critical = sum(1 for i in all_issues if i.severity == "critical")
        major    = sum(1 for i in all_issues if i.severity == "major")
        minor    = sum(1 for i in all_issues if i.severity == "minor")

        # 评分：满分100，扣分：critical -15，major -5，minor -2
        score = max(0.0, 100.0 - critical * 15 - major * 5 - minor * 2)

        suggestions = []
        if critical > 0:
            suggestions.append(f"存在 {critical} 个严重问题，必须在定稿前修复")
        if major > 0:
            suggestions.append(f"存在 {major} 个主要问题，建议修复")
        if score >= 85:
            suggestions.append("整体质量良好，建议人工审阅技术参数后定稿")
        elif score >= 60:
            suggestions.append("建议重点检查技术要求章节的数值参数和单位")
        else:
            suggestions.append("质量较低，建议重新生成或大幅修改")

        report = ValidationReport(
            overall_score=round(score, 1),
            issues=all_issues,
            suggestions=suggestions,
            requires_human_review=critical > 0 or score < 70,
        )
        return report.to_dict()
