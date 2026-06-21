"""Unit tests for MCQ stem/option splitter and LLM response parser.

mcq/__init__.py pulls in reranker → sentence_transformers → numpy 2.x issue.
utils.py and parser.py themselves are clean; load via importlib to bypass
the package __init__.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import types
import pytest

_MCQ_DIR = pathlib.Path(__file__).parents[1] / "src" / "services" / "qa" / "mcq"


def _load(name: str, filename: str, package: str = ""):
    spec = importlib.util.spec_from_file_location(name, _MCQ_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    if package:
        mod.__package__ = package
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_utils = _load("_mcq_utils", "utils.py")
split_stem_and_options = _utils.split_stem_and_options

# formatter.py has no heavy deps — load cleanly, then stub the package reference
_formatter = _load("_mcq_formatter", "formatter.py")

# Provide a minimal fake package so parser's relative import resolves
_pkg = types.ModuleType("src.services.qa.mcq")
_pkg.__path__ = [str(_MCQ_DIR)]  # type: ignore[attr-defined]
_pkg.__package__ = "src.services.qa.mcq"
_pkg.formatter = _formatter  # type: ignore[attr-defined]
sys.modules.setdefault("src.services.qa.mcq", _pkg)
sys.modules["src.services.qa.mcq.formatter"] = _formatter

_parser = _load("_mcq_parser", "parser.py", package="src.services.qa.mcq")
parse_mcq_response = _parser.parse_mcq_response
validate_mcq_output = _parser.validate_mcq_output
MCQParseError = _parser.MCQParseError
_strip_code_fences = _parser._strip_code_fences
_normalize_answer = _parser._normalize_answer

# ── split_stem_and_options ────────────────────────────────────────────────────

MCQ_BLOCK = """以下哪项描述了正确的密封顺序？
A. 先填角，再贴合面
B. 先贴合面，再填角
C. 顺序不重要
D. 以上均不正确"""


class TestSplitStemAndOptions:
    def test_extracts_stem(self):
        stem, _ = split_stem_and_options(MCQ_BLOCK)
        assert "以下哪项" in stem

    def test_extracts_four_options(self):
        _, options = split_stem_and_options(MCQ_BLOCK)
        assert set(options.keys()) == {"A", "B", "C", "D"}

    def test_option_text_stripped(self):
        _, options = split_stem_and_options(MCQ_BLOCK)
        assert options["A"] == "先填角，再贴合面"

    def test_empty_string(self):
        stem, options = split_stem_and_options("")
        assert stem == "" and options == {}

    def test_stem_without_options(self):
        stem, options = split_stem_and_options("没有选项的题目。")
        assert "没有选项" in stem and options == {}

    def test_period_delimiter(self):
        _, opts = split_stem_and_options("题干\nA. 一\nB. 二")
        assert "A" in opts and "B" in opts

    def test_chinese_delimiter(self):
        _, opts = split_stem_and_options("题干\nA、一\nB、二")
        assert "A" in opts and "B" in opts

    def test_lines_after_options_ignored(self):
        text = "题干\nA. 一\nB. 二\n注意事项（这行应被忽略）"
        _, opts = split_stem_and_options(text)
        assert "注意事项" not in str(opts)


# ── _strip_code_fences ────────────────────────────────────────────────────────

class TestStripCodeFences:
    def test_strips_json_fence(self):
        assert _strip_code_fences("```json\n{\"a\":1}\n```") == '{"a":1}'

    def test_strips_plain_fence(self):
        assert _strip_code_fences("```\n{\"a\":1}\n```") == '{"a":1}'

    def test_no_fence_unchanged(self):
        raw = '{"a":1}'
        assert _strip_code_fences(raw) == raw

    def test_empty_returns_empty(self):
        assert _strip_code_fences("") == ""


# ── _normalize_answer ─────────────────────────────────────────────────────────

class TestNormalizeAnswer:
    def test_uppercases(self):
        assert _normalize_answer("b") == "B"

    def test_strips_whitespace(self):
        assert _normalize_answer("  C  ") == "C"

    def test_fullwidth_to_ascii(self):
        assert _normalize_answer("Ａ") == "A"
        assert _normalize_answer("Ｄ") == "D"

    def test_non_string_returns_empty(self):
        assert _normalize_answer(None) == ""
        assert _normalize_answer(123) == ""


# ── parse_mcq_response ────────────────────────────────────────────────────────

class TestParseMcqResponse:
    def test_standard_json(self):
        raw = '{"final_answer":"B","reason":"正确"}'
        assert parse_mcq_response(raw)["final_answer"] == "B"

    def test_json_in_prose(self):
        raw = '分析如下 {"final_answer":"C","reason":"理由"} 完毕'
        assert parse_mcq_response(raw)["final_answer"] == "C"

    def test_lowercase_normalised(self):
        raw = '{"final_answer":"b","reason":"理由"}'
        assert parse_mcq_response(raw)["final_answer"] == "B"

    def test_answer_alias(self):
        raw = '{"answer":"D","reason":"理由"}'
        assert parse_mcq_response(raw)["final_answer"] == "D"

    def test_code_fence_stripped(self):
        raw = '```json\n{"final_answer":"A","reason":"理由"}\n```'
        assert parse_mcq_response(raw)["final_answer"] == "A"

    def test_empty_raises(self):
        with pytest.raises(MCQParseError):
            parse_mcq_response("")

    def test_no_json_raises(self):
        with pytest.raises(MCQParseError):
            parse_mcq_response("纯文字，无 JSON")

    def test_invalid_json_raises(self):
        with pytest.raises(MCQParseError):
            parse_mcq_response("{bad json}")


# ── validate_mcq_output ───────────────────────────────────────────────────────

class TestValidateMcqOutput:
    OPTS = {"A": "一", "B": "二", "C": "三"}

    def test_valid_passes(self):
        validate_mcq_output({"final_answer": "A", "reason": "合理"}, self.OPTS)

    def test_missing_answer_raises(self):
        with pytest.raises(MCQParseError, match="缺少"):
            validate_mcq_output({"reason": "理由"}, self.OPTS)

    def test_answer_not_in_options_raises(self):
        with pytest.raises(MCQParseError, match="不在选项"):
            validate_mcq_output({"final_answer": "Z", "reason": "理由"}, self.OPTS)

    def test_missing_reason_raises(self):
        with pytest.raises(MCQParseError, match="缺少 reason"):
            validate_mcq_output({"final_answer": "A"}, self.OPTS)

    def test_banned_phrase_raises(self):
        with pytest.raises(MCQParseError, match="禁用短语"):
            validate_mcq_output(
                {"final_answer": "A", "reason": "语义类型不一致，无法作答"},
                self.OPTS,
            )
