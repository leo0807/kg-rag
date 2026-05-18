
from __future__ import annotations

import re

from .types import MCQType


_ORDER_STEM = re.compile(r'顺序|先后|排序|流程|步骤排列|推荐.*选用')
_ORDER_OPT = re.compile(r'[①②③④⑤⑥⑦⑧⑨].*[-—→].*[①②③④⑤⑥⑦⑧⑨]')
_NUMERIC_OPT = re.compile(r'\d+(?:\.\d+)?\s*(mm|μm|英寸|°C|℃|MPa|kg|秒|分钟|小时|N|kN|°|度)')
_DEF_STEM = re.compile(r'目的是|作用是|定义|是指|属于|含义|为了')
_COND_STEM = re.compile(r'什么情况下|何时|不可接受|可接受|适用于|不适用|应当|不应|必须|禁止')


def is_order(stem: str, options: dict[str, str]) -> bool:
    if _ORDER_STEM.search(stem):
        return True
    matched = sum(1 for v in options.values() if _ORDER_OPT.search(v))
    return matched >= max(2, len(options) - 1)


def is_numeric(stem: str, options: dict[str, str]) -> bool:
    matched = sum(1 for v in options.values() if _NUMERIC_OPT.search(v))
    return matched >= max(2, len(options) - 1)


def is_definition(stem: str, options: dict[str, str]) -> bool:
    return bool(_DEF_STEM.search(stem))


def is_condition(stem: str, options: dict[str, str]) -> bool:
    return bool(_COND_STEM.search(stem))


def detect_mcq_type(stem: str, options: dict[str, str]) -> MCQType:
    if is_order(stem, options):
        return MCQType.ORDER
    if is_definition(stem, options):
        return MCQType.DEFINITION
    if is_numeric(stem, options):
        return MCQType.NUMERIC
    if is_condition(stem, options):
        return MCQType.CONDITION
    return MCQType.GENERAL
