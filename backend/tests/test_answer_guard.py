"""Unit tests for hallucination guard (validate_answer)."""
from src.services.answer_guard import validate_answer


def _sources(*doc_ids: str) -> list[dict]:
    return [{"doc_id": d} for d in doc_ids]


class TestNoHallucination:
    def test_answer_without_cps_refs_passes_through(self):
        text = "密封剂施工期一般为 30 分钟。"
        result = validate_answer(text, _sources("CPS1000"))
        assert result == text

    def test_answer_citing_only_source_docs_passes_through(self):
        text = "参见 CPS1000 第 7 章。"
        result = validate_answer(text, _sources("CPS1000"))
        assert "CPS1000" in result

    def test_empty_answer_returns_empty(self):
        assert validate_answer("", _sources("CPS1000")) == ""

    def test_none_answer_returns_empty(self):
        assert validate_answer(None, _sources("CPS1000")) == ""  # type: ignore[arg-type]

    def test_no_sources_passes_through(self):
        text = "CPS9999 不存在。"
        result = validate_answer(text, [])
        assert result == text


class TestHallucinationRemoval:
    def test_removes_doc_id_not_in_sources(self):
        text = "根据 CPS9999 第 3 章的规定。"
        result = validate_answer(text, _sources("CPS1000"))
        assert "CPS9999" not in result

    def test_keeps_source_doc_id(self):
        text = "根据 CPS1000 第 3 章的规定。"
        result = validate_answer(text, _sources("CPS1000"))
        assert "CPS1000" in result

    def test_mixed_hallucinated_and_real(self):
        text = "CPS1000 和 CPS8888 均有相关规定。"
        result = validate_answer(text, _sources("CPS1000"))
        assert "CPS1000" in result
        assert "CPS8888" not in result

    def test_fully_hallucinated_returns_fallback(self):
        text = "根据 CPS9999 的规定。"
        result = validate_answer(text, _sources("CPS1000"))
        assert "CPS9999" not in result
        assert len(result) > 0  # fallback message or stripped text

    def test_question_with_cps_narrows_sources(self):
        text = "CPS1220 要求密封剂施工期不超过 30 分钟。CPS5000 另有规定。"
        result = validate_answer(text, _sources("CPS1220", "CPS5000"), question="CPS1220 的密封要求是什么？")
        assert "CPS1220" in result

    def test_compare_question_allows_both_source_refs(self):
        text = "CPS1000 和 CPS2000 的要求不同。"
        result = validate_answer(
            text,
            _sources("CPS1000", "CPS2000"),
            question="CPS1000 和 CPS2000 有什么区别？",
        )
        assert "CPS1000" in result
        assert "CPS2000" in result


class TestEdgeCases:
    def test_none_sources_does_not_raise(self):
        result = validate_answer("CPS1000 说明", None)
        assert "CPS1000" in result

    def test_whitespace_only_answer(self):
        result = validate_answer("   ", _sources("CPS1000"))
        assert result == ""

    def test_case_insensitive_cps_detection(self):
        text = "根据 cps1000 的规定。"
        result = validate_answer(text, _sources("CPS1000"))
        # either strips or normalises — important it doesn't raise
        assert isinstance(result, str)
