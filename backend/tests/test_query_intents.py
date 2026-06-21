"""Unit tests for query intent detection (CPS count questions)."""
from src.services.query_intents import (
    is_total_cps_count_question,
    build_total_cps_count_answer,
)


class TestIsTotalCpsCountQuestion:
    def test_recognises_count_question(self):
        assert is_total_cps_count_question("系统里有多少本 CPS 文档？") is True

    def test_recognises_ji_ben(self):
        assert is_total_cps_count_question("CPS 共有几本？") is True

    def test_recognises_total_word(self):
        assert is_total_cps_count_question("总共有多少 CPS？") is True

    def test_does_not_match_without_cps(self):
        assert is_total_cps_count_question("文档一共有多少？") is False

    def test_does_not_match_without_count_word(self):
        assert is_total_cps_count_question("CPS 的内容是什么？") is False

    def test_none_input_is_false(self):
        assert is_total_cps_count_question(None) is False

    def test_empty_string_is_false(self):
        assert is_total_cps_count_question("") is False

    def test_recognises_yigong(self):
        assert is_total_cps_count_question("CPS 一共多少本？") is True


class TestBuildCountAnswer:
    def test_includes_count(self):
        answer = build_total_cps_count_answer(42)
        assert "42" in answer

    def test_includes_cps_mention(self):
        answer = build_total_cps_count_answer(10)
        assert "CPS" in answer

    def test_zero_count(self):
        answer = build_total_cps_count_answer(0)
        assert "0" in answer
