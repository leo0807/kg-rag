"""
Unit tests for src/services/generation/validator.py
Tests SpecValidator methods (pure Python, no DB/LLM dependencies).
"""
import pytest
from src.services.generation.validator import (
    SpecValidator,
    Issue,
    ValidationReport,
    _REQUIRED_SECTIONS,
)


# ── Issue / ValidationReport dataclasses ─────────────────────────────────────

def test_issue_defaults():
    issue = Issue(severity="critical", section="1", description="Missing")
    assert issue.suggestion == ""


def test_validation_report_to_dict_keys():
    report = ValidationReport(overall_score=80.0)
    d = report.to_dict()
    assert set(d.keys()) == {"overall_score", "requires_human_review", "issues", "suggestions"}


def test_validation_report_score_preserved():
    report = ValidationReport(overall_score=72.5)
    assert report.to_dict()["overall_score"] == 72.5


def test_validation_report_issues_serialized():
    issue = Issue("major", "3", "Problem", "Fix it")
    report = ValidationReport(overall_score=90.0, issues=[issue])
    d = report.to_dict()
    assert len(d["issues"]) == 1
    assert d["issues"][0]["severity"] == "major"
    assert d["issues"][0]["suggestion"] == "Fix it"


# ── check_structure ───────────────────────────────────────────────────────────

def _full_sections():
    """Minimal sections dict satisfying all required sections with enough words."""
    base = " ".join(["word"] * 25)
    return {sec: base for sec in _REQUIRED_SECTIONS}


def test_check_structure_no_issues_when_all_present():
    v = SpecValidator()
    issues = v.check_structure(_full_sections())
    critical = [i for i in issues if i.severity == "critical"]
    assert len(critical) == 0


def test_check_structure_critical_for_missing_section():
    v = SpecValidator()
    sections = _full_sections()
    del sections["1"]
    issues = v.check_structure(sections)
    assert any(i.severity == "critical" and i.section == "1" for i in issues)


def test_check_structure_critical_for_empty_section():
    v = SpecValidator()
    sections = _full_sections()
    sections["2"] = "   "   # whitespace only
    issues = v.check_structure(sections)
    assert any(i.severity == "critical" and i.section == "2" for i in issues)


def test_check_structure_major_for_short_content():
    v = SpecValidator()
    sections = _full_sections()
    sections["9"] = "short"  # < 20 words, non-required section
    issues = v.check_structure(sections)
    assert any(i.severity == "major" and i.section == "9" for i in issues)


# ── check_references ─────────────────────────────────────────────────────────

def test_check_references_no_issues_when_all_cited():
    v = SpecValidator()
    sections = {"2": "CPS1234 and CPS5678 are referenced here.", "3": "terms"}
    issues = v.check_references(sections, ["CPS1234", "CPS5678"])
    assert not issues


def test_check_references_minor_for_uncited_doc():
    v = SpecValidator()
    sections = {"2": "nothing here"}
    issues = v.check_references(sections, ["CPS9999"])
    assert any(i.severity == "minor" for i in issues)


def test_check_references_bad_format_flagged():
    v = SpecValidator()
    # CPS 12 is not 4-digit format
    sections = {"2": "references", "5": "refer to CPS 12 in this section"}
    issues = v.check_references(sections, [])
    assert any("格式" in i.description for i in issues)


def test_check_references_empty_doc_ids_ok():
    v = SpecValidator()
    sections = {"2": "no docs needed"}
    issues = v.check_references(sections, [])
    assert issues == []


# ── check_numerical ───────────────────────────────────────────────────────────

def test_check_numerical_no_issues_when_values_have_units():
    v = SpecValidator()
    sections = {"6": "温度应为 120℃，压力 2.5 MPa，时间 30 min"}
    issues = v.check_numerical(sections)
    # No bare-number-without-unit issues expected
    bare_issues = [i for i in issues if "数值" in i.description]
    assert len(bare_issues) == 0


def test_check_numerical_major_for_vague_word():
    v = SpecValidator()
    sections = {"6": "约 120 个零件需要处理，大约在此范围内完成"}
    issues = v.check_numerical(sections)
    assert any("模糊" in i.description or "约" in i.description for i in issues)


def test_check_numerical_skips_non_priority_sections():
    v = SpecValidator()
    # Section "4" is not in high_priority {6,7,8}
    sections = {"4": "数值 100 200 300 无单位"}
    issues = v.check_numerical(sections)
    assert issues == []


# ── check_terminology ─────────────────────────────────────────────────────────

def test_check_terminology_no_issues_when_many_terms():
    v = SpecValidator()
    sections = {
        "3": "3.1 焊接\n3.2 压力\n3.3 温度\n3.4 检测",
        "5": "内容",
    }
    issues = v.check_terminology(sections)
    assert issues == []


def test_check_terminology_minor_when_few_terms():
    v = SpecValidator()
    sections = {
        "3": "3.1 焊接\n3.2 压力",   # only 2 definitions
        "5": "some content",
    }
    issues = v.check_terminology(sections)
    assert any(i.severity == "minor" for i in issues)


# ── validate_full ─────────────────────────────────────────────────────────────

def test_validate_full_returns_dict():
    v = SpecValidator()
    result = v.validate_full(_full_sections(), {}, [])
    assert isinstance(result, dict)
    assert "overall_score" in result
    assert "issues" in result


def test_validate_full_score_between_0_and_100():
    v = SpecValidator()
    result = v.validate_full(_full_sections(), {}, [])
    assert 0.0 <= result["overall_score"] <= 100.0


def test_validate_full_low_score_requires_review():
    v = SpecValidator()
    # Empty sections → many critical issues → low score
    result = v.validate_full({}, {}, [])
    assert result["requires_human_review"] is True


def test_validate_full_high_quality_no_review():
    v = SpecValidator()
    # Full valid sections with units and plenty of terms
    sections = {sec: " ".join(["word"] * 30) for sec in _REQUIRED_SECTIONS}
    sections["3"] = "3.1 焊接\n3.2 压力\n3.3 温度\n"
    # Sections 6,7,8 have values with units
    sections["6"] = "温度应为 120℃，压力 2.5 MPa，时间 30 min，尺寸 5 mm"
    sections["7"] = "载荷 500 N·m，间隙 0.5 mm，精度 μm 级"
    sections["8"] = "检测频率 1 次/h，样本量 10%，温度 25℃"
    result = v.validate_full(sections, {}, [])
    # Score should be reasonably high
    assert result["overall_score"] >= 50.0
