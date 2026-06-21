"""Unit tests for answer text humanization."""
from src.services.answer_humanizer import humanize_answer_text


class TestBoilerplateStripping:
    def test_strips_leading_gen_boilerplate(self):
        text = "根据提供的规范内容，密封剂施工期为 30 分钟。"
        result = humanize_answer_text(text)
        assert "根据提供的规范内容，" not in result
        assert "密封剂施工期" in result

    def test_strips_retrieval_prefix(self):
        text = "根据检索到的规范，应使用 PR-1422 密封剂。"
        result = humanize_answer_text(text)
        assert "根据检索到的规范，" not in result
        assert "PR-1422" in result

    def test_strips_current_results_prefix(self):
        text = "根据当前检索结果，施工温度不低于 15℃。"
        result = humanize_answer_text(text)
        assert "根据当前检索结果，" not in result

    def test_replaces_zongershuo_with_simple(self):
        text = "综上所述，应按规范操作。"
        result = humanize_answer_text(text)
        assert "综上所述" not in result
        assert "简单说" in result

    def test_strips_closing_boilerplate(self):
        text = "正文内容。综上所述，请遵照执行。"
        result = humanize_answer_text(text)
        assert "综上所述" not in result

    def test_strips_keyi_kanchu_prefix(self):
        text = "可以看出，密封要求较为严格。"
        result = humanize_answer_text(text)
        assert "可以看出，" not in result

    def test_chained_prefixes_stripped(self):
        text = "根据提供的规范内容，根据当前检索结果，要求如下。"
        result = humanize_answer_text(text)
        assert "根据" not in result or result.startswith("要求")


class TestFormatting:
    def test_collapses_triple_newlines(self):
        text = "第一段\n\n\n\n第二段"
        result = humanize_answer_text(text)
        assert "\n\n\n" not in result

    def test_empty_input_returns_empty(self):
        assert humanize_answer_text("") == ""

    def test_none_input_returns_empty(self):
        assert humanize_answer_text(None) == ""  # type: ignore[arg-type]

    def test_fixes_heading_without_space(self):
        # "###标题" → "### 标题"
        text = "###密封要求"
        result = humanize_answer_text(text)
        assert "### 密封要求" in result

    def test_deduplicates_trailing_punctuation(self):
        text = "按规范操作。。"
        result = humanize_answer_text(text)
        assert "。。" not in result

    def test_removes_leading_comma(self):
        text = "，按规范操作。"
        result = humanize_answer_text(text)
        assert not result.startswith("，")

    def test_replaces_nbsp_with_space(self):
        text = "密封 要求"
        result = humanize_answer_text(text)
        assert " " not in result

    def test_plain_text_preserved(self):
        text = "应使用 PR-1422 密封剂，施工期为 30 分钟。"
        result = humanize_answer_text(text)
        assert "PR-1422" in result
        assert "30 分钟" in result
