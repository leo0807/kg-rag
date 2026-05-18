
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MCQType(str, Enum):
    ORDER = 'T3_order'
    NUMERIC = 'T4_numeric'
    DEFINITION = 'T1_definition'
    CONDITION = 'T6_condition'
    GENERAL = 'T0_general'


@dataclass(frozen=True)
class MCQQuestion:
    stem: str
    options: dict[str, str]
    mcq_type: MCQType | None = None


@dataclass(frozen=True)
class MCQTypeMeta:
    code: MCQType
    name: str
    label: str


MCQ_TYPE_META = {
    MCQType.ORDER: MCQTypeMeta(MCQType.ORDER, '步骤顺序题', '分析步骤顺序'),
    MCQType.NUMERIC: MCQTypeMeta(MCQType.NUMERIC, '数值规格题', '核对数值规格'),
    MCQType.DEFINITION: MCQTypeMeta(MCQType.DEFINITION, '概念定义题', '匹配规范定义'),
    MCQType.CONDITION: MCQTypeMeta(MCQType.CONDITION, '条件判据题', '判定适用条件'),
    MCQType.GENERAL: MCQTypeMeta(MCQType.GENERAL, '通用客观题', '通用分析'),
}
