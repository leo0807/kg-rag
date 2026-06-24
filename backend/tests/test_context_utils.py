"""Unit tests for conversation context utilities."""
from src.services.context_utils import (
    trim_conversation_history,
    trim_conversation_history_for_question,
    extract_question_doc_ids,
    normalize_doc_hints,
    resolve_retrieval_doc_id,
)

HISTORY = [
    {"role": "user", "content": "第一轮问题"},
    {"role": "assistant", "content": "第一轮回答"},
    {"role": "user", "content": "第二轮问题"},
    {"role": "assistant", "content": "第二轮回答"},
    {"role": "user", "content": "第三轮问题"},
    {"role": "assistant", "content": "第三轮回答"},
    {"role": "user", "content": "第四轮问题"},
    {"role": "assistant", "content": "第四轮回答"},
]


class TestTrimHistory:
    def test_empty_history_returns_empty(self):
        assert trim_conversation_history([]) == []

    def test_none_history_returns_empty(self):
        assert trim_conversation_history(None) == []

    def test_keeps_last_n_rounds(self):
        result = trim_conversation_history(HISTORY, max_rounds=2)
        assert len(result) == 4  # 2 rounds × 2 messages

    def test_default_max_rounds_is_three(self):
        result = trim_conversation_history(HISTORY)
        assert len(result) == 6  # 3 rounds

    def test_filters_system_messages(self):
        history = [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "用户消息"},
            {"role": "assistant", "content": "助手回答"},
        ]
        result = trim_conversation_history(history, max_rounds=3)
        assert all(m["role"] != "system" for m in result)

    def test_strips_empty_content(self):
        history = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "有内容的消息"},
            {"role": "assistant", "content": "回答"},
        ]
        result = trim_conversation_history(history, max_rounds=3)
        assert all(m["content"] for m in result)

    def test_handles_non_dict_items_gracefully(self):
        history = ["string", {"role": "user", "content": "正常"}, None]
        result = trim_conversation_history(history, max_rounds=3)  # type: ignore[arg-type]
        assert len(result) == 1

    def test_max_rounds_zero_returns_empty(self):
        result = trim_conversation_history(HISTORY, max_rounds=0)
        assert result == []


class TestTrimForQuestion:
    def test_cps_question_always_returns_empty(self):
        result = trim_conversation_history_for_question("CPS1220 的密封要求？", HISTORY)
        assert result == []

    def test_non_cps_question_trims_normally(self):
        result = trim_conversation_history_for_question("密封剂怎么用？", HISTORY)
        assert len(result) > 0

    def test_none_question_trims_normally(self):
        result = trim_conversation_history_for_question(None, HISTORY)
        assert len(result) > 0


class TestExtractDocIds:
    def test_extracts_single_cps_id(self):
        assert extract_question_doc_ids("CPS1220 的规定") == ["CPS1220"]

    def test_extracts_multiple_cps_ids(self):
        ids = extract_question_doc_ids("CPS1000 和 CPS2000 有什么不同？")
        assert "CPS1000" in ids
        assert "CPS2000" in ids

    def test_deduplicates(self):
        ids = extract_question_doc_ids("CPS1000 和 CPS1000 重复提到")
        assert ids.count("CPS1000") == 1

    def test_empty_question_returns_empty(self):
        assert extract_question_doc_ids(None) == []
        assert extract_question_doc_ids("") == []

    def test_uppercases_output(self):
        ids = extract_question_doc_ids("cps1000 的要求")
        assert all(d == d.upper() for d in ids)

    def test_does_not_extract_partial_match(self):
        # CPS embedded in longer alphanumeric should not match (word boundary)
        ids = extract_question_doc_ids("XCPS1000Y 不应被提取")
        assert ids == []


class TestNormalizeDocHints:
    def test_empty_returns_empty(self):
        assert normalize_doc_hints(None) == []
        assert normalize_doc_hints([]) == []

    def test_strips_and_uppercases(self):
        result = normalize_doc_hints(["  cps1000  ", "cps2000"])
        assert result == ["CPS1000", "CPS2000"]

    def test_deduplicates(self):
        result = normalize_doc_hints(["CPS1000", "CPS1000"])
        assert result == ["CPS1000"]

    def test_filters_blank_entries(self):
        result = normalize_doc_hints(["CPS1000", "", "   "])
        assert result == ["CPS1000"]


class TestResolveRetrievalDocId:
    def test_single_cps_in_question(self):
        result = resolve_retrieval_doc_id("CPS1220 的要求是什么？")
        assert result == "CPS1220"

    def test_multiple_cps_in_question_returns_empty(self):
        result = resolve_retrieval_doc_id("CPS1000 和 CPS2000 的区别？")
        assert result == ""

    def test_falls_back_to_single_hint(self):
        result = resolve_retrieval_doc_id("密封剂要求", ["CPS1220"])
        assert result == "CPS1220"

    def test_multiple_hints_returns_empty(self):
        result = resolve_retrieval_doc_id("密封剂要求", ["CPS1220", "CPS2000"])
        assert result == ""

    def test_question_id_takes_priority_over_hint(self):
        result = resolve_retrieval_doc_id("CPS1000 的要求", ["CPS9999"])
        assert result == "CPS1000"

    def test_none_question_uses_hints(self):
        result = resolve_retrieval_doc_id(None, ["CPS1220"])
        assert result == "CPS1220"
