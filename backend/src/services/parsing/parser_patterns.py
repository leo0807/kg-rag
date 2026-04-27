from __future__ import annotations

import re

_TITLE_RE = r'([^\n]{2,80})'

SECTION_PATTERNS = [
    re.compile(
        r'^(\d{1,2}(?:\.\d{1,2}){0,3})[ \t\u3000]+' + _TITLE_RE,
        re.MULTILINE,
    ),
    re.compile(
        r'^([A-Z]\.\d{1,2}(?:\.\d{1,2}){0,2})[ \t\u3000]+' + _TITLE_RE,
        re.MULTILINE,
    ),
    re.compile(
        r'^(第[一二三四五六七八九十百千]+[章节条款])[ \t\u3000　]*' + _TITLE_RE,
        re.MULTILINE,
    ),
    re.compile(
        r'^(X{0,3}(?:IX|IV|V?I{0,3})\.)[ \t]+' + _TITLE_RE,
        re.MULTILINE,
    ),
]

SECTION_PATTERN = SECTION_PATTERNS[0]

_TOC_HINT_RE  = re.compile(r'(目录|目\s*录|contents?|table\s+of\s+contents|toc)', re.IGNORECASE)
_TOC_TRAIL_RE = re.compile(r'(?:\.{3,}|·{3,}|…{2,})\s*\d{1,4}\s*$')
_PAGE_TRAIL_RE = re.compile(r'\s\d{1,4}\s*$')

_BODY_ITEM_RE = re.compile(
    r'^[型类级种].{0,2}[：:]'
    r'|[±°℃]\s*\d'
    r'|处理\s*\d+\s*[hH时]'
    r'|[<>≤≥]\s*\d'
    r'|\d+\s*[hH时]\s*后'
)

_UNIT_ONLY_RE = re.compile(
    r'^(?:minutes?|hours?|days?|weeks?|months?|gallon|gallons|ounce|ounces)$',
    re.IGNORECASE,
)

_CATALOG_HINT_RE = re.compile(
    r'('
    r'\bP/N\b|'
    r'\bRTV-\d[\w-]*\b|'
    r'\bDAPCO\d[\w-]*\b|'
    r'\bCPM\d[\w-]*\b|'
    r'#\d+|'
    r'\b\d+/\d+-(?:gallon|ounce)\b|'
    r'\b\d+\s*(?:分钟|天|周|月|days?|weeks?|months?|minutes?|hours?)\b|'
    r'或等效'
    r')',
    re.IGNORECASE,
)

_MODEL_CODE_TOKEN_RE   = re.compile(r'\b(?:[A-Z]{2,}\d[\w-]*|\d{4,})\b')
_TITLE_CONTINUATION_RE = re.compile(r'(?:\(|（)[^()（）]{0,200}$')
_TRAILING_CONNECTOR_RE = re.compile(
    r'(?:and|or|with|for|to|of|the|a|an|及|和|与|或|并|、|/|-|—)$', re.IGNORECASE
)
_REFERENCE_TITLE_RE = re.compile(
    r'^(?:节|章|条|before\b|after\b|refer\b|as per\b)', re.IGNORECASE
)

_NON_TITLE = re.compile(
    r'^('
    r'密级|保密|内部|公开|受控|非受控|'
    r'版本[:：]|版\s*本|Rev\.|版次|'
    r'CPS\d|HB\d|Q/\w|第\d+页|共\d+页|'
    r'\d{4}[-年]\d{1,2}[-月]|'
    r'中国商用|中国航空|上海飞机|'
    r'[\d\.\-\s]+$'
    r')',
    re.IGNORECASE,
)

TITLE_BLACKLIST = [
    r"密级[：:].+",
    r"^(内部|秘密|机密|公开|受控|非受控)$",
    r"版本[：:]\s*[A-Za-z]",
    r"Rev\.[A-Za-z]",
    r"第\s*\d+\s*页",
    r"共\s*\d+\s*页",
    r"\d{4}[-年]\d{1,2}[-月]\d{0,2}",
    r"^(编制|审核|批准|校对|会签)[：:]",
    r"^(发布|实施)[：:]",
    r"^(发布日期|实施日期)[：:]",
    r"中国商用飞机有限责任公司",
    r"中国航空",
    r"上海飞机",
    r"^CPS\d+",
    r"^HB\d+",
    r"^Q/\w+",
    r"^[\d\.\-\s]+$",
]

_BLACKLIST_RE = [re.compile(p) for p in TITLE_BLACKLIST]
