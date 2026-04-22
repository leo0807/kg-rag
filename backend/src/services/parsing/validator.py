"""
文档解析质量验证服务

对已入库文档执行一组规则检查，生成结构化验证报告。
验证结果包含：overall valid/invalid、问题列表（level + code + detail）、统计摘要。

验证规则
--------
E001  MISSING_TITLE       文档 title 为空
E002  MISSING_DOC_ID      doc_id 为空
E003  NO_SECTIONS         章节数为 0
W001  SUSPICIOUS_DOC_ID   doc_id 不匹配 CPS\\d+ 格式
W002  FEW_SECTIONS        章节数 < 3（可能解析不完整）
W003  EMPTY_SECTION       某章节 content 为空或极短（< 10 字符）
W004  HIERARCHY_GAP       章节编号存在跳跃（如 1→3，缺少 2）
W005  DUPLICATE_NUMBER    章节编号重复
W006  LONG_TITLE_AS_SECTION  章节 title 超过 60 字（可能是整段正文被误作标题）
I001  SHORT_CONTENT_AVG   平均章节内容较短（< 100 字），可能 OCR/解析质量不高
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

_CPS_RE = re.compile(r'^CPS\d+', re.IGNORECASE)
_NUM_RE = re.compile(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?')


@dataclass
class Issue:
    level:  Literal["error", "warning", "info"]
    code:   str
    detail: str


@dataclass
class ValidationResult:
    doc_id:  str
    valid:   bool                      # True = 无 error 级别问题
    score:   int                       # 0-100 综合得分
    issues:  list[Issue] = field(default_factory=list)
    stats:   dict        = field(default_factory=dict)


def validate_document(driver, doc_id: str) -> ValidationResult:
    """
    从 Neo4j 读取文档数据并执行全部验证规则，返回 ValidationResult。
    """
    issues: list[Issue] = []

    # ── 查询文档基本信息 ──────────────────────────────────────────────────────
    with driver.session() as s:
        doc_row = s.run(
            "MATCH (d:Document {name:$id}) RETURN d.title AS title, d.name AS doc_id",
            id=doc_id,
        ).single()
        if not doc_row:
            return ValidationResult(
                doc_id=doc_id, valid=False, score=0,
                issues=[Issue("error", "E004", f"文档 {doc_id} 不存在于图数据库")],
            )

        title  = (doc_row["title"] or "").strip()
        actual_doc_id = (doc_row["doc_id"] or "").strip()

        sections_result = s.run("""
            MATCH (d:Document {name:$id})-[:HAS_SECTION]->(sec:Section)
            RETURN sec.number AS number, sec.title AS title, sec.content AS content
            ORDER BY sec.number
        """, id=doc_id)
        sections = [dict(r) for r in sections_result]

    # ── 规则检查 ──────────────────────────────────────────────────────────────

    # E001 标题缺失
    if not title:
        issues.append(Issue("error", "E001", "文档标题为空"))

    # E002 doc_id 缺失
    if not actual_doc_id:
        issues.append(Issue("error", "E002", "文档编号为空"))

    # W001 doc_id 格式异常
    elif not _CPS_RE.match(actual_doc_id):
        issues.append(Issue("warning", "W001", f"doc_id '{actual_doc_id}' 不符合 CPS\\d+ 格式"))

    # E003 无章节
    section_count = len(sections)
    if section_count == 0:
        issues.append(Issue("error", "E003", "文档没有任何已解析章节（section_count = 0）"))
    elif section_count < 3:
        issues.append(Issue("warning", "W002", f"章节数仅 {section_count} 个，可能解析不完整"))

    # W003 空章节内容
    empty_sections = [
        s for s in sections
        if not (s.get("content") or "").strip() or len((s.get("content") or "").strip()) < 10
    ]
    for sec in empty_sections[:5]:   # 最多报 5 个，避免噪音
        issues.append(Issue(
            "warning", "W003",
            f"章节 {sec['number']} 「{(sec.get('title') or '')[:30]}」内容为空或极短"
        ))

    # W004 / W005 章节编号校验
    numbers = [s.get("number") or "" for s in sections]
    seen_nums: set[str] = set()
    for num in numbers:
        if num in seen_nums:
            issues.append(Issue("warning", "W005", f"章节编号 {num} 重复出现"))
        seen_nums.add(num)

    top_nums = sorted(set(
        int(_NUM_RE.match(n).group(1))
        for n in numbers
        if _NUM_RE.match(n)
    ))
    if len(top_nums) >= 2:
        for a, b in zip(top_nums, top_nums[1:]):
            if b - a > 1:
                issues.append(Issue(
                    "warning", "W004",
                    f"顶级章节编号跳跃：{a} → {b}（中间缺少章节）"
                ))

    # W006 标题过长（可能误把正文当标题）
    long_title_sections = [
        s for s in sections if len((s.get("title") or "")) > 60
    ]
    for sec in long_title_sections[:3]:
        issues.append(Issue(
            "warning", "W006",
            f"章节 {sec['number']} 标题过长（{len(sec.get('title',''))} 字），疑似正文误识别为标题"
        ))

    # I001 平均内容长度
    if section_count > 0:
        avg_len = sum(
            len((s.get("content") or "").strip()) for s in sections
        ) // section_count
        if avg_len < 100:
            issues.append(Issue(
                "info", "I001",
                f"章节平均内容长度仅 {avg_len} 字，可能 OCR/解析质量偏低"
            ))
    else:
        avg_len = 0

    # ── 计算综合得分 (0-100) ───────────────────────────────────────────────────
    deductions = sum({
        "error":   25,
        "warning": 8,
        "info":    2,
    }[iss.level] for iss in issues)
    score = max(0, 100 - deductions)
    has_errors = any(iss.level == "error" for iss in issues)

    return ValidationResult(
        doc_id  = doc_id,
        valid   = not has_errors,
        score   = score,
        issues  = issues,
        stats   = {
            "section_count":     section_count,
            "empty_sections":    len(empty_sections),
            "avg_content_len":   avg_len,
            "duplicate_numbers": sum(1 for iss in issues if iss.code == "W005"),
            "hierarchy_gaps":    sum(1 for iss in issues if iss.code == "W004"),
            "title":             title,
        },
    )


def validate_all(driver) -> dict:
    """
    批量验证所有文档，返回汇总统计。
    """
    with driver.session() as s:
        doc_ids = [r["doc_id"] for r in s.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
        )]

    results = []
    for doc_id in doc_ids:
        try:
            r = validate_document(driver, doc_id)
            results.append(r)
        except Exception as e:
            logger.warning("验证文档 %s 失败: %s", doc_id, e)

    valid_count   = sum(1 for r in results if r.valid)
    invalid_count = len(results) - valid_count
    zero_sections = sum(1 for r in results if r.stats.get("section_count", 0) == 0)
    avg_score     = (sum(r.score for r in results) // len(results)) if results else 0

    return {
        "total":         len(results),
        "valid":         valid_count,
        "invalid":       invalid_count,
        "zero_sections": zero_sections,
        "avg_score":     avg_score,
        "documents": [
            {
                "doc_id": r.doc_id,
                "valid":  r.valid,
                "score":  r.score,
                "issues": [{"level": i.level, "code": i.code, "detail": i.detail} for i in r.issues],
                "stats":  r.stats,
            }
            for r in results
        ],
    }
