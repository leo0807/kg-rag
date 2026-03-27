import pytest
from src.services.parser import extract_meta, extract_sections, clean_content
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