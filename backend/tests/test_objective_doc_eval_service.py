from src.services.evaluation.objective_doc_eval_metrics import (
    _apply_choice_support_override,
    _infer_answer_from_option_content,
)
from src.services.evaluation.objective_doc_eval_parser import (
    _build_objective_retrieval_query,
    _parse_question_block,
    _parse_objective_llm_response,
)
from src.services.evaluation.objective_doc_eval_runner import (
    answer_objective_question as _answer_objective_question,
)
from unittest.mock import MagicMock, patch


def test_parse_objective_llm_response_infers_choice_from_reason_when_final_answer_is_empty():
    raw = '{"final_answer":"","reason":"根据题干分析，正确选项是D，因为只有D符合规范要求。"}'

    answer, reason = _parse_objective_llm_response(raw, "choice", ["A", "B", "C", "D"])

    assert answer == "D"
    assert reason == "根据题干分析，正确选项是D，因为只有D符合规范要求。"


def test_parse_objective_llm_response_infers_judge_answer_from_reason_when_final_answer_is_empty():
    raw = '{"final_answer":"","reason":"该做法不符合要求，因此判断为错。"}'

    answer, reason = _parse_objective_llm_response(raw, "judge", [])

    assert answer == "错"
    assert reason == "该做法不符合要求，因此判断为错。"


def test_parse_objective_llm_response_parses_malformed_multi_choice_json():
    raw = '{final_answer:"BCD",reason:"选项B、C、D均正确。"}'

    answer, reason = _parse_objective_llm_response(raw, "multi_choice", ["A", "B", "C", "D"])

    assert answer == "BCD"
    assert reason == "选项B、C、D均正确。"


def test_parse_objective_llm_response_cleans_reason_prefix_noise():
    raw = '{final_answer:"C",reason:"final_answer:\\"C\\",,（根据证据支持度纠正为 A）"}'

    answer, reason = _parse_objective_llm_response(raw, "choice", ["A", "B", "C", "D"])

    assert answer == "C"
    assert reason == "（根据证据支持度纠正为 A）"


def test_parse_objective_llm_response_infers_answer_from_natural_language_hint():
    raw = "依据规范，正确答案为B，因此选择B。"

    answer, reason = _parse_objective_llm_response(raw, "choice", ["A", "B", "C", "D"])

    assert answer == "B"
    assert "正确答案" in reason


def test_build_objective_retrieval_query_prefers_core_keywords():
    question = "对于用异丙醇修型方法描述不正确的是（C）？"
    options = [
        {"label": "A", "text": "将修整工具浸入异丙醇溶剂中或将异丙醇溶剂涂在修整工具上。"},
        {"label": "B", "text": "甩掉工具上的多余液体。"},
        {"label": "C", "text": "可以直接将异丙醇施加到密封剂上。"},
        {"label": "D", "text": "注意避免将异丙醇溶剂弄到密封剂层之间或零件表面和密封剂之间。"},
    ]

    query = _build_objective_retrieval_query(question, options)

    assert "异丙醇" in query
    assert "修型" in query
    assert "密封剂" in query
    assert "不正确" not in query


def test_parse_question_block_detects_multi_choice_from_answer_key():
    block = [
        "4. 关于对贴合面密封，下列描述正确的是：（BCD）",
        "A. 在密封剂施工期内，将密封剂施加到两个相对的贴合面上；",
        "B. 密封剂要均匀的覆盖整个贴合面；",
        "C. 在密封剂的施工期或者挤出寿命之内，施加充分夹紧的力使挤出的密封剂串形成连续的可见的密封剂膜并获得连续的挤出；",
        "D. 在零件贴合面之间的涂胶，仍然看作是金属对金属的接触，紧密贴合在一起。",
    ]

    item = _parse_question_block(block, 4)

    assert item is not None
    assert item["question_type"] == "multi_choice"
    assert item["answer_key"] == "BCD"
    assert "（BCD）" not in item["question"]


def test_answer_objective_question_uses_stem_only_on_primary_retrieval():
    question = "通用密封的目的是______、______、______、______。"
    options = [
        {"label": "A", "text": "客舱增压、整体油箱、防腐蚀、防漏油"},
        {"label": "B", "text": "防漏水、防腐蚀、防漏油、防漏气"},
        {"label": "C", "text": "气动性能的改进、防漏气、客舱增压、整体油箱"},
        {"label": "D", "text": "整体油箱、防腐蚀、防漏水、防漏气"},
    ]

    calls = []

    def fake_retrieval(driver, query, strategy, top_k, use_hyde=False, hyde_alpha=0.5, doc_id=""):
        calls.append({
            "query": query,
            "strategy": strategy,
            "top_k": top_k,
            "use_hyde": use_hyde,
            "hyde_alpha": hyde_alpha,
            "doc_id": doc_id,
        })
        return [], {}

    with patch("src.services.evaluation.objective_doc_eval_service.DO_RETRIEVAL", side_effect=fake_retrieval):
        result = _answer_objective_question(
            question=question,
            options=options,
            question_type="choice",
            answer_key="",
            strategy="parallel",
            top_k=5,
            driver=MagicMock(),
        )

    assert result["predicted_answer"] == ""
    assert "通用密封" in calls[0]["query"]
    assert "整体油箱" not in calls[0]["query"]
    assert calls[0]["doc_id"] == ""
    assert calls[1]["strategy"] == "graph_augmented"
    assert calls[1]["use_hyde"] is False
    assert calls[2]["use_hyde"] is True
    assert "整体油箱" in calls[2]["query"]


def test_apply_choice_support_override_prefers_better_supported_option():
    context = "通用密封的目的是防漏水、防腐蚀、防漏油、防漏气。"
    options = [
        {"label": "A", "text": "客舱增压、整体油箱、防腐蚀、防漏油"},
        {"label": "B", "text": "防漏水、防腐蚀、防漏油、防漏气"},
        {"label": "C", "text": "气动性能的改进、防漏气、客舱增压、整体油箱"},
        {"label": "D", "text": "整体油箱、防腐蚀、防漏水、防漏气"},
    ]

    answer, reason = _apply_choice_support_override(context, options, "D", "模型误判")

    assert answer == "B"
    assert "证据支持度" in reason


def test_apply_choice_support_override_can_fill_blank_answer_from_context():
    context = "沿接缝涂密封剂胶，以形成一个基本密封胶缝的方法称为包胶密封，应涂在密封边界的紧固件处。"
    options = [
        {"label": "A", "text": "贴合面密封、压力侧"},
        {"label": "B", "text": "包胶密封、紧固件处"},
        {"label": "C", "text": "填角密封、压力侧"},
        {"label": "D", "text": "对接密封、接触表面"},
    ]

    answer, reason = _apply_choice_support_override(context, options, "", "根据规范描述可定位到选项文本。")

    assert answer == "B"
    assert "推断为 B" in reason


def test_infer_answer_from_option_content_uses_reason_text():
    options = [
        {"label": "A", "text": "贴合面密封、压力侧"},
        {"label": "B", "text": "包胶密封、紧固件处"},
        {"label": "C", "text": "填角密封、压力侧"},
        {"label": "D", "text": "对接密封、接触表面"},
    ]

    answer = _infer_answer_from_option_content(
        "根据规范描述，这与选项中的包胶密封、紧固件处描述一致。",
        "choice",
        options,
    )

    assert answer == "B"


def test_answer_objective_question_uses_graph_augmented_as_soft_supplement():
    options = [
        {"label": "A", "text": "客舱增压、整体油箱、防腐蚀、防漏油"},
        {"label": "B", "text": "防漏水、防腐蚀、防漏油、防漏气"},
        {"label": "C", "text": "气动性能的改进、防漏气、客舱增压、整体油箱"},
        {"label": "D", "text": "整体油箱、防腐蚀、防漏水、防漏气"},
    ]
    calls = []

    def fake_retrieval(driver, query, strategy, top_k, use_hyde=False, hyde_alpha=0.5, doc_id=""):
        calls.append({
            "strategy": strategy,
            "use_hyde": use_hyde,
            "doc_id": doc_id,
        })
        section = {
            "chunk_id": f"{strategy}_1",
            "doc_id": "CPS1000" if strategy != "parallel" or use_hyde else "CPS1304",
            "number": "6.2",
            "title": "通用密封",
            "content": "通用密封的目的是防漏水、防腐蚀、防漏油、防漏气。",
            "page_idx": 0,
            "seq_index": 10,
        }
        return ([section], {section["chunk_id"]: 10.0})

    fake_llm = MagicMock()
    fake_llm.chat.return_value = '{"final_answer":"","reason":"根据规范描述可知其对应防漏水、防腐蚀、防漏油、防漏气。"}'

    with patch("src.services.evaluation.objective_doc_eval_service.DO_RETRIEVAL", side_effect=fake_retrieval), \
         patch("src.services.evaluation.objective_doc_eval_service.get_llm_service", return_value=fake_llm), \
         patch("src.services.evaluation.objective_doc_eval_service._expand_objective_graph_neighbors", return_value=[]), \
         patch("src.services.evaluation.objective_doc_eval_service._expand_objective_local_neighbors", return_value=[]):
        result = _answer_objective_question(
            question="通用密封的目的是______、______、______、______。",
            options=options,
            question_type="choice",
            answer_key="",
            strategy="parallel",
            top_k=5,
            driver=MagicMock(),
        )

    assert calls[0]["strategy"] == "parallel"
    assert calls[1]["strategy"] == "graph_augmented"
    assert calls[2]["use_hyde"] is True
    assert all(call["doc_id"] == "" for call in calls)
    assert result["predicted_answer"] == "B"
    assert any(ref.startswith("CPS1000") for ref in result["source_refs"])
