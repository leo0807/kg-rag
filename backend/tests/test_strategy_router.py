import pytest
from src.services.qa.strategy_router import select_strategy


def test_comparison_questions():
    s, _ = select_strategy("对比两种密封剂")
    assert s == "parallel"

    s, _ = select_strategy("A 和 B 的区别")
    assert s == "parallel"

    s, _ = select_strategy("这两种材料有什么差异")
    assert s == "parallel"


def test_multi_hop_questions():
    s, _ = select_strategy("规范要求是什么?")
    assert s == "multi_hop"

    s, _ = select_strategy("另一章节有什么补充?")
    assert s == "multi_hop"


def test_param_questions():
    s, _ = select_strategy("钻铆的扭矩参数是多少?")
    assert s == "graph_augmented"

    s, _ = select_strategy("固化温度是多少度?")
    assert s == "graph_augmented"

    s, _ = select_strategy("允许的公差范围是多少")
    assert s == "graph_augmented"


def test_procedure_questions():
    s, _ = select_strategy("装配的步骤是什么?")
    assert s == "graph_augmented"

    s, _ = select_strategy("如何涂覆密封剂?")
    assert s == "graph_augmented"

    s, _ = select_strategy("操作流程是怎么的")
    assert s == "graph_augmented"


def test_default_fallback():
    s, _ = select_strategy("密封胶的固化时间")
    assert s == "parallel"

    s, _ = select_strategy("什么是通用密封")
    assert s == "parallel"


def test_reason_is_nonempty_string():
    s, reason = select_strategy("任意问题")
    assert isinstance(reason, str)
    assert len(reason) > 0


def test_returns_tuple():
    result = select_strategy("test")
    assert isinstance(result, tuple)
    assert len(result) == 2
