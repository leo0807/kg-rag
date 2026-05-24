"""根据问题特征自动选择最优检索策略。"""


def select_strategy(question: str) -> tuple[str, str]:
    """
    Args:
        question: 用户问题原文

    Returns:
        (strategy_name, reason_explanation)
    """
    q = question.lower()

    if any(kw in q for kw in ["对比", "比较", "区别", "不同", "差异"]):
        return "parallel", "对比型问题适合并行全文+向量检索"

    if any(kw in q for kw in ["引用", "参照", "规范要求", "另一"]):
        return "multi_hop", "跨文档引用问题适合多跳推理"

    if any(kw in q for kw in ["力矩", "温度", "压力", "公差", "参数", "数值", "范围", "极限"]):
        return "graph_augmented", "工艺约束参数问题适合图谱增强检索"

    if any(kw in q for kw in ["如何", "步骤", "流程", "怎么", "操作", "程序", "顺序"]):
        return "graph_augmented", "步骤/流程型问题适合图谱增强检索"

    return "parallel", "通用问题使用并行检索"
