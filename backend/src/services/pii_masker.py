"""
services/pii_masker.py
PII（个人信息）检测与脱敏，用于导出接口和日志。
"""
from __future__ import annotations

import re

# 编译正则提升性能
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 编制人/审核人/批准人 + 2~4 汉字姓名
    (re.compile(r"(编制|审核|批准|拟制|校核)[：:\s]*[一-鿿]{2,4}"), r"\1：***"),
    # 手机号
    (re.compile(r"\b1[3-9]\d{9}\b"), "***-****-****"),
    # 座机
    (re.compile(r"\b\d{3,4}-\d{7,8}\b"), "***-*******"),
    # 邮箱
    (re.compile(r"[\w.+-]+@[\w.-]+\.\w+"), "***@***.***"),
    # 身份证
    (re.compile(r"\b\d{17}[\dXx]\b"), "***...**"),
]


class PIIMasker:
    """对文本中的 PII 信息进行替换脱敏。"""

    def mask(self, text: str) -> str:
        if not text:
            return text
        result = text
        for pattern, replacement in _PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    def mask_dict(self, d: dict, fields: list[str]) -> dict:
        """对字典中指定字段进行脱敏，返回新字典（不修改原始对象）。"""
        out = dict(d)
        for field in fields:
            if field in out and isinstance(out[field], str):
                out[field] = self.mask(out[field])
        return out


# 模块级单例，供导出接口直接使用
pii_masker = PIIMasker()
