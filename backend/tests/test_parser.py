import pytest
from src.services.parser import (
    extract_meta,
    extract_sections,
    clean_content,
    _is_likely_toc_page,
    _looks_like_toc,
    _match_section_heading,
    _normalize_heading_candidate,
    _merge_wrapped_heading,
    _should_extend_heading_title,
    _trim_front_matter_headings,
    is_likely_section_title,
)
from pathlib import Path

class TestCleanContent:
    """clean_content 是纯函数，最容易测试——输入字符串，输出字符串"""

    def test_removes_footer(self):
        """专有信息声明应该被删掉"""
        text = "7.1 管件端头准备\n正文内容\n专有信息声明\n本文件含有中国商用飞机有限责任公司的专有信息。未经中国商用飞机有限责任公司书面授权，不可基于任何目的将本文件所含信息的全部或部分内容进行直接或间接的复制、\n引用、披露或使用。如果取得书面授权，应当将本声明完整地加入所有副本中。非授权接收人应立即告知中国商用飞机有限责任公司并退回本文件及任何副本。中国商用飞机\n有限责任公司保留本文件一切版权。"
        result = clean_content(text)
        assert "专有信息声明" not in result
        assert "正文内容" in result

    def test_removes_page_number(self):
        """页码应该被删掉"""
        text = "正文内容\nCPS1220版 本:C 第5页 共10页\n继续正文"
        result = clean_content(text)
        assert "第5页" not in result
        assert "正文内容" in result
        assert "继续正文" in result

    def test_collapses_blank_lines(self):
        """多余空行应该被压缩成最多两个换行"""
        text = "第一段\n\n\n\n\n第二段"
        result = clean_content(text)
        assert "\n\n\n" not in result

    def test_empty_string(self):
        """空字符串不应该报错"""
        result = clean_content("")
        assert result == ""

# ── 测试正则提取 ──────────────────────────────────────────────

class TestExtractMeta:
    """测试封面元数据提取，用固定字符串模拟封面内容"""

    def test_extracts_doc_id_and_version(self):
        import re
        text = "CPS1220版本:C\n密级：内部"
        match = re.search(r'(CPS\d+)版本[:：]([A-Z])', text)
        assert match is not None
        assert match.group(1) == "CPS1220"
        assert match.group(2) == "C"

    def test_extracts_issue_date(self):
        import re
        text = "2021-04-27发布 2021-04-27 实施"
        match = re.search(r'(\d{4}-\d{2}-\d{2})发布', text)
        assert match is not None
        assert match.group(1) == "2021-04-27"

    def test_no_match_returns_none(self):
        import re
        text = "这是一段没有规范编号的文字"
        match = re.search(r'(CPS\d+)版本[:：]([A-Z])', text)
        assert match is None


# ── 测试章节识别 ──────────────────────────────────────────────

class TestSectionPattern:
    """测试章节号识别正则"""

    def test_matches_top_level(self):
        import re
        pattern = re.compile(
            r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s+([\u4e00-\u9fff\w\/\-]+)$',
            re.MULTILINE
        )
        text = "1 范围\n本工艺规范..."
        matches = pattern.findall(text)
        assert len(matches) == 1
        assert matches[0] == ("1", "范围")

    def test_matches_nested(self):
        import re
        pattern = re.compile(
            r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s+([\u4e00-\u9fff\w\/\-]+)$',
            re.MULTILINE
        )
        text = "7.1.1 采用棘轮型切割器"
        matches = pattern.findall(text)
        assert len(matches) == 1
        assert matches[0] == ("7.1.1", "采用棘轮型切割器")

    def test_does_not_match_date(self):
        import re
        pattern = re.compile(
            r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s+([\u4e00-\u9fff\w\/\-]+)$',
            re.MULTILINE
        )
        # 日期不应该被识别为章节
        text = "2021-04-27发布"
        matches = pattern.findall(text)
        assert len(matches) == 0


class TestTocFiltering:
    def test_detects_toc_lines(self):
        assert _looks_like_toc("1.2 密封要求 .......... 12")
        assert _looks_like_toc("目录")
        assert _looks_like_toc("Table of Contents")

    def test_keeps_real_headings(self):
        assert not _looks_like_toc("1.2 密封要求")
        assert is_likely_section_title("1.2", "1.2 密封要求")

    def test_detects_toc_page_from_multiple_index_lines(self):
        assert _is_likely_toc_page([
            "1 范围 1",
            "2 引用文件 2",
            "3 要求 3",
        ])

    def test_normalizes_heading_with_page_number_on_body_page(self):
        normalized = _normalize_heading_candidate("1 范围 1", on_toc_page=False)

        assert normalized == "1 范围"
        assert _match_section_heading(normalized) == ("1", "范围")

    def test_keeps_toc_entry_unchanged_on_toc_page(self):
        normalized = _normalize_heading_candidate("1 范围 1", on_toc_page=True)

        assert normalized == "1 范围 1"
        assert not is_likely_section_title("1", "范围 1")

    def test_trims_fake_front_matter_before_scope(self):
        headings = [
            {"number": "0.1", "title": "修订记录"},
            {"number": "0.2", "title": "目录"},
            {"number": "1", "title": "范围（Scope）"},
            {"number": "2", "title": "引用文件"},
        ]

        trimmed = _trim_front_matter_headings(headings)

        assert [item["number"] for item in trimmed] == ["1", "2"]

    def test_rejects_zero_prefixed_decimal_noise(self):
        assert not is_likely_section_title("0.5", "inch on the bolt bar")
        assert not is_likely_section_title("0", r"4\10\ ")

    def test_rejects_bilingual_list_items_as_sections(self):
        assert not is_likely_section_title(
            "0.5",
            "inch on the bolt bar, install preloading indicating washer components",
        )

    def test_anchor_prefers_real_main_body_over_front_matter_items(self):
        headings = [
            {"number": "0.5", "title": "inch on the bolt bar"},
            {"number": "1", "title": "250 型涂胶枪"},
            {"number": "1", "title": "范围（Scope）"},
            {"number": "2", "title": "引用文件（Normative References）"},
            {"number": "3", "title": "定义"},
        ]

        trimmed = _trim_front_matter_headings(headings)

        assert [item["title"] for item in trimmed][:2] == ["范围（Scope）", "引用文件（Normative References）"]

    def test_rejects_catalog_like_tail_items_after_real_sections(self):
        assert not is_likely_section_title("10", "229777 1/10-gallon")
        assert not is_likely_section_title("12", "盘司 P/N 220923 或等效")
        assert not is_likely_section_title("14", "229775 20-ounce")
        assert not is_likely_section_title("15", "minutes")
        assert not is_likely_section_title("16", "DAPCO2100 CPM9500-1 — 10 分钟 7天")
        assert not is_likely_section_title("20", "盘司定位器 -")
        assert not is_likely_section_title("32", "Multi-")
        assert not is_likely_section_title("45", "X 30 X #62 30 X")
        assert not is_likely_section_title("45", "X 1- 45 X")
        assert not is_likely_section_title("30", "X 1- 20 X")

    def test_keeps_real_bilingual_section_titles(self):
        assert is_likely_section_title("9.4", "检验（Inspection）")
        assert is_likely_section_title("1", "范围（Scope）")


class TestWrappedHeadingMerge:
    def test_detects_unclosed_parenthesis_as_continuation(self):
        assert _should_extend_heading_title(
            "需要湿安装的衬套和轴承的密封(Sealing for Wet Assembly Bush and"
        )

    def test_merges_wrapped_bilingual_heading(self):
        merged = _merge_wrapped_heading(
            "7.5.16.3 需要湿安装的衬套和轴承的密封(Sealing for Wet Assembly Bush and",
            "Bearing)",
        )

        assert merged == (
            "7.5.16.3",
            "需要湿安装的衬套和轴承的密封(Sealing for Wet Assembly Bush and Bearing)",
        )

    def test_does_not_merge_complete_heading_with_body_text(self):
        merged = _merge_wrapped_heading(
            "7.5.16.3 需要湿安装的衬套和轴承的密封(Sealing for Wet Assembly Bush and Bearing)",
            "衬套安装前应检查孔壁状态。",
        )

        assert merged is None
        assert _match_section_heading(
            "7.5.16.3 需要湿安装的衬套和轴承的密封(Sealing for Wet Assembly Bush and Bearing)"
        ) == (
            "7.5.16.3",
            "需要湿安装的衬套和轴承的密封(Sealing for Wet Assembly Bush and Bearing)",
        )
