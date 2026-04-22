from __future__ import annotations

import re
import logging
import pdfplumber
from pathlib import Path
from ...models.schemas import DocumentSchema, SectionSchema

logger = logging.getLogger(__name__)

# ── 章节模式列表（按优先级排列）─────────────────────────────────────────────────
# 每个模式捕获两组：group(1)=章节号，group(2)=标题文本
# 标题：行内任意字符，2-80 位（[^\n] 避免跨行匹配）

_TITLE_RE = r'([^\n]{2,80})'   # group(2) 占位符：匹配同一行内 2-80 个任意字符

SECTION_PATTERNS = [
    # 1. 数字编号：1 / 1.1 / 1.1.1 / 1.1.1.1（最常见）
    re.compile(
        r'^(\d{1,2}(?:\.\d{1,2}){0,3})[ \t\u3000]+' + _TITLE_RE,
        re.MULTILINE,
    ),
    # 2. 字母编号：A.1 / B.2.1
    re.compile(
        r'^([A-Z]\.\d{1,2}(?:\.\d{1,2}){0,2})[ \t\u3000]+' + _TITLE_RE,
        re.MULTILINE,
    ),
    # 3. 中文数字：第一章 / 第二节 / 第三条 / 第十款
    re.compile(
        r'^(第[一二三四五六七八九十百千]+[章节条款])[ \t\u3000　]*' + _TITLE_RE,
        re.MULTILINE,
    ),
    # 4. 罗马数字：I. II. III. IV. VI. IX.（前置空行隔离避免正文误匹配）
    re.compile(
        r'^(X{0,3}(?:IX|IV|V?I{0,3})\.)[ \t]+' + _TITLE_RE,
        re.MULTILINE,
    ),
]

# 向后兼容：保留 SECTION_PATTERN 指向第一个（最常用）模式
SECTION_PATTERN = SECTION_PATTERNS[0]

_TOC_HINT_RE = re.compile(r'(目录|目\s*录|contents?|table\s+of\s+contents|toc)', re.IGNORECASE)
_TOC_TRAIL_RE = re.compile(r'(?:\.{3,}|·{3,}|…{2,})\s*\d{1,4}\s*$')
_PAGE_TRAIL_RE = re.compile(r'\s\d{1,4}\s*$')


def _looks_like_toc(title: str) -> bool:
    """识别目录项 / 页码引导行，避免把目录误当成正文标题。"""
    t = re.sub(r'\s+', ' ', title).strip()
    if not t:
        return False
    if _TOC_HINT_RE.search(t):
        return True
    if _TOC_TRAIL_RE.search(t):
        return True
    # 目录项常以短标题 + 页码结束，例如 "1.2 密封要求  12"
    if _PAGE_TRAIL_RE.search(t) and len(t) <= 48:
        return True
    return False


def _is_likely_toc_page(lines: list[str]) -> bool:
    """根据整页行文本判断该页是否更像目录页。"""
    normalized = [re.sub(r'\s+', ' ', line).strip() for line in lines if line.strip()]
    if not normalized:
        return False
    if any(_TOC_HINT_RE.search(line) for line in normalized):
        return True

    toc_like_lines = sum(1 for line in normalized if _looks_like_toc(line))
    heading_with_page_trail = sum(
        1
        for line in normalized
        if _match_section_heading(line) and _PAGE_TRAIL_RE.search(line)
    )
    return toc_like_lines >= 4 or heading_with_page_trail >= 3

def fix_token_spacing(text: str) -> str:
    """
    修复 pdfplumber extract_words 拼接后缺少空格的问题：
    - 数字/ASCII 字母后紧跟中文 → 加空格（如 "6.1.8.1在密封" → "6.1.8.1 在密封"）
    - 中文后紧跟数字/ASCII 字母 → 加空格（如 "密封A" → "密封 A"）
    已有空格不重复添加。
    """
    # ASCII数字/字母 后跟 中文
    text = re.sub(r'([0-9A-Za-z\.])([\u4e00-\u9fff\u3400-\u4dbf])', r'\1 \2', text)
    # 中文 后跟 ASCII数字/字母（排除小数点后的数字，避免"第3.1节"被破坏）
    text = re.sub(r'([\u4e00-\u9fff\u3400-\u4dbf])([0-9A-Za-z])', r'\1 \2', text)
    return text


# 章节标题中不允许出现的正文特征模式（用于排除假阳性）
_BODY_ITEM_RE = re.compile(
    r'^[型类级种].{0,2}[：:]'       # "1型：..." "2类：..." 等列举项开头
    r'|[±°℃]\s*\d'                  # 温度参数（120±2℃、60℃ 等）
    r'|处理\s*\d+\s*[hH时]'         # "处理3h" 等时间描述
    r'|[<>≤≥]\s*\d'                 # 不等式约束（≥99%、≤0.5%）
    r'|\d+\s*[hH时]\s*后'           # "3h后"
    # 注：抽真空/真空袋/密封胶条 等工艺名词也可出现在章节标题中，已移除
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

_MODEL_CODE_TOKEN_RE = re.compile(r'\b(?:[A-Z]{2,}\d[\w-]*|\d{4,})\b')
_TITLE_CONTINUATION_RE = re.compile(r'(?:\(|（)[^()（）]{0,200}$')
_TRAILING_CONNECTOR_RE = re.compile(r'(?:and|or|with|for|to|of|the|a|an|及|和|与|或|并|、|/|-|—)$', re.IGNORECASE)


def _match_section_heading(text: str) -> tuple[str, str] | None:
    """从单行文本中提取章节号和标题。"""
    candidate = (text or "").strip()
    if not candidate:
        return None

    for pat in SECTION_PATTERNS:
        match = pat.match(candidate)
        if match:
            return match.group(1), match.group(2).strip()

    text_fixed = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', candidate)
    if text_fixed != candidate:
        for pat in SECTION_PATTERNS:
            match = pat.match(text_fixed)
            if match:
                return match.group(1), match.group(2).strip()
    return None


def _normalize_heading_candidate(text: str, on_toc_page: bool) -> str:
    """
    在非目录页上，修正被页码拼到标题末尾的章节行，例如：
    `1 范围 1` -> `1 范围`
    """
    candidate = (text or "").strip()
    if not candidate or on_toc_page:
        return candidate

    match = _match_section_heading(candidate)
    if not match:
        return candidate

    number, title = match
    trimmed_title = _PAGE_TRAIL_RE.sub("", title).strip()
    if not trimmed_title or trimmed_title == title:
        return candidate
    if not is_likely_section_title(number, trimmed_title):
        return candidate
    return f"{number} {trimmed_title}"


def _should_extend_heading_title(title: str) -> bool:
    """判断标题是否像是被 PDF/OCR 折到了下一行。"""
    normalized = re.sub(r'\s+', ' ', (title or "")).strip()
    if not normalized:
        return False
    if normalized.count("(") > normalized.count(")"):
        return True
    if normalized.count("（") > normalized.count("）"):
        return True
    if _TITLE_CONTINUATION_RE.search(normalized):
        return True
    if _TRAILING_CONNECTOR_RE.search(normalized):
        return True
    return False


def _merge_wrapped_heading(
    current_text: str,
    next_text: str,
) -> tuple[str, str] | None:
    """
    尝试把被换行拆开的章节标题拼回一行。
    仅在当前标题明显未结束时触发，避免误吞正文第一行。
    """
    current_match = _match_section_heading(current_text)
    if not current_match:
        return None

    number, title = current_match
    if not _should_extend_heading_title(title):
        return None

    next_normalized = re.sub(r'\s+', ' ', (next_text or "")).strip()
    if not next_normalized:
        return None
    if _match_section_heading(next_normalized):
        return None

    merged_match = _match_section_heading(f"{current_text} {next_normalized}")
    if not merged_match:
        return None
    return merged_match


def is_likely_section_title(number: str, title: str) -> bool:
    """
    判断匹配到的 (number, title) 是否为真实章节标题，还是正文列举项或目录条目的误匹配。
    """
    title = title.strip()
    normalized_title = re.sub(r'\s+', ' ', title)

    # 0. 明确的目录项 / TOC 行
    if _looks_like_toc(title):
        return False

    # 0b. 单独的包装/时间单位，不应作为章节标题（如 "minutes"）
    if _UNIT_ONLY_RE.fullmatch(normalized_title):
        return False

    # 1. 排除目录条目：标题包含连续3个以上的点（TOC 页码引导点）
    if re.search(r'\.{3,}', title):
        return False
    # 2. 排除正文列举项特征
    if _BODY_ITEM_RE.search(title):
        return False
    # 3. 标题过长且开头不像章节标题
    #    双语标题（中文名─英文名）可达 60+ 字符，阈值设为 70
    #    开头允许中文、字母数字、以及 ─—（连接符）
    if len(title) > 70 and not re.match(
        r'^[\u4e00-\u9fff\w─—]{2,20}[（(：: ─—]', title
    ):
        return False
    # 4. 章节号小数点后 ≥ 3 位才视为小数参数值（2.830 类）
    #    两位如 7.10 是合法章节号；实际扭矩值 2.83/10.17 已由 Rule 6（计量单位）拦截
    parts = number.split(".")
    if len(parts) == 2 and len(parts[1]) >= 3 and parts[1].isdigit():
        return False
    # 4b. 规范正文不应以 0 / 0.x 作为正式章节号；这类命中通常来自前言列表、小数值或 OCR 噪声
    if number == "0" or number.startswith("0."):
        return False
    # 5. 章节号以"0"开头的两位数（03、05、06）通常是表格行序号
    if re.match(r'^0\d$', number):
        return False
    # 6. 包含计量单位的行（扭矩、压力、频率等参数值）
    if re.search(
        r'\d+\s*[（(]?\s*\d*\.?\d*\s*'
        r'(lbf|N·m|N\.m|nm|kg|mm|cm|MPa|kPa|°C|℃|psi|rpm|Hz|in\b)',
        title, re.IGNORECASE,
    ):
        return False
    # 7. 标题以图引用结尾（正文引用句，非章节标题）
    #    只过滤"如图X-XX所示；"结尾型，不过滤中间含图引用的步骤描述
    if re.search(r'如图\s*[\d\w]+[-–]\d+[^。]*所示\s*[；;，,。]?\s*$', title):
        return False
    # 8. 以计量词结尾的短句（"1.5 周，..." 类）
    if re.search(r'[周米克吨磅英寸毫米厘米秒分钟小时]\s*[，,；;。]?\s*$', title):
        return False
    # 9b. 极短标题（去除标点后 < 4 个字符），通常是正文片段
    stripped = re.sub(r'[；;，,。.!！?？\s]', '', title)
    if len(stripped) < 4 and not re.fullmatch(r'[\u4e00-\u9fff]{2,3}', stripped):
        return False
    # 9. 纯数字/分隔符行（表格列数据，如 "115/125 143/153 -"）
    if re.match(r'^[\d\s/\-–—.]+$', title):
        return False
    # 9c. 物料/BOM/料号清单行：常含料号、包装单位、固化时间、P/N、型号编码
    visible = re.sub(r'\s+', '', normalized_title)
    natural_chars = len(re.findall(r'[\u4e00-\u9fffA-Za-z]', normalized_title))
    code_tokens = _MODEL_CODE_TOKEN_RE.findall(normalized_title)
    if (
        _CATALOG_HINT_RE.search(normalized_title)
        or (
            code_tokens
            and natural_chars < max(6, int(len(visible) * 0.45))
            and re.search(r'[\d#/\-–—]', normalized_title)
        )
    ):
        return False
    # 9d. 断裂残句 / OCR 切碎的词块（如 "Multi-"、"盘司定位器 -"）
    if normalized_title.endswith(("-", "–", "—")):
        return False
    if re.fullmatch(r'[a-z][a-z\-]{1,20}', normalized_title):
        return False
    # 9e. OCR / 表格残片：仅由单字母占位和数字组成（如 "X 1- 45 X"）
    alpha_tokens = re.findall(r'[A-Za-z]+', normalized_title)
    digit_tokens = re.findall(r'\d+', normalized_title)
    if (
        not re.search(r'[\u4e00-\u9fff]', normalized_title)
        and len(alpha_tokens) >= 2
        and all(len(token) == 1 for token in alpha_tokens)
        and (digit_tokens or re.search(r'[#/\\\-–—]', normalized_title))
    ):
        return False
    # 9a. OCR 噪声 / 符号碎片，不应进入章节目录（如 "4\\10\\"）
    if re.search(r'[\\|]{2,}', title):
        return False
    if len(re.findall(r'[\u4e00-\u9fffA-Za-z]', title)) < 2:
        return False
    # 10. 图/表标题不应被当作章节标题
    if re.match(r'^(图|表)\s*\d+', title):
        return False
    return True


def _normalize_anchor_number(number: str) -> str:
    """将候选章节号规整成适合正文锚点判断的形式。"""
    normalized = (number or "").strip()
    normalized = normalized.rstrip("、.．)）")
    return normalized


def _trim_front_matter_headings(headings: list[dict]) -> list[dict]:
    """
    丢弃正文首个一级章节之前的伪标题。
    很多规范在封面/目录/修订记录页上会出现被误判成 heading 的行，
    但真正的正文通常从 `1 范围（Scope）` 或首个一级数字章节开始。
    """
    if not headings:
        return headings

    # 第一优先级：显式命中 “1 范围（Scope）”
    for idx, heading in enumerate(headings):
        number = _normalize_anchor_number(str(heading.get("number", "")))
        title = str(heading.get("title", "")).strip()
        if number == "1" and re.search(r"(范围|scope)", title, re.IGNORECASE):
            return headings[idx:]

    anchor_idx = None
    for idx, heading in enumerate(headings):
        number = _normalize_anchor_number(str(heading.get("number", "")))
        title = str(heading.get("title", "")).strip()
        if number == "1":
            anchor_idx = idx
            # 其次要求后续很快出现 2 章，避免把前言中的偶发 "1 xxx" 当成正文起点。
            lookahead = [
                _normalize_anchor_number(str(item.get("number", "")))
                for item in headings[idx + 1: idx + 6]
            ]
            if "2" in lookahead:
                break

    if anchor_idx is None or anchor_idx == 0:
        return headings

    return headings[anchor_idx:]


def clean_content(text: str) -> str:
    # 清洗章节内容，去掉页脚声明和页码
    # 去掉专有信息声明
    text = re.sub(
        r'专有信息声明.*?有限责任公司保留本文件一切版权。',
        '', text, flags=re.DOTALL
    )
    # 去掉页眉页码
    text = re.sub(r'CPS\d+版\s*本:\s*[A-Z]\s*第\d+页\s*共\d+页', '', text)
    # 去掉多余空行
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text

def extract_refs(sections: list[dict]) -> list[str]:
    # 从引用文件章节提取被引用的规范编号
    for section in sections:
        # 第2章固定是引用文件
        if section["number"] == "2":
            refs = re.findall(r"\b(C[PD]S\d+)\b", section["content"])
            return list(set(refs))
    return []

# 封面非标题行特征：密级标注、版本、编号、日期、公司名、页码等
_NON_TITLE = re.compile(
    r'^('
    r'密级|保密|内部|公开|受控|非受控|'          # 密级标注
    r'版本[:：]|版\s*本|Rev\.|版次|'             # 版本
    r'CPS\d|HB\d|Q/\w|第\d+页|共\d+页|'        # 编号 / 页码
    r'\d{4}[-年]\d{1,2}[-月]|'                  # 日期
    r'中国商用|中国航空|上海飞机|'               # 公司名
    r'[\d\.\-\s]+$'                              # 纯数字/分隔符行
    r')',
    re.IGNORECASE,
)


def _extract_title_fallback(cover_text: str, pdf_path: Path) -> str:
    """当正则未能从封面提取标题时的多级 fallback"""

    # 优先从文件名提取（文件名格式：CPS1002_J_整体油箱的密封_422413.pdf）
    fn_match = re.search(r'CPS\d+_[A-Z]_([\u4e00-\u9fff\w\-·]+?)_\d+\.pdf', pdf_path.name, re.IGNORECASE)
    if fn_match:
        candidate = fn_match.group(1).strip()
        if len(candidate) >= 4:
            return candidate

    # 从封面文本中逐行筛选：跳过非标题行，取第一个有效行
    lines = [l.strip() for l in cover_text.split('\n') if l.strip()]
    for line in lines:
        if len(line) < 4:
            continue
        if _NON_TITLE.match(line):
            continue
        # 要求至少包含一个中文字符
        if not re.search(r'[\u4e00-\u9fff]', line):
            continue
        return line

    # 最终 fallback：取第二行（保留原有行为）
    return lines[1] if len(lines) > 1 else ""


# 封面干扰项黑名单（字号优先策略使用）
TITLE_BLACKLIST = [
    r"密级[：:].+",                        # 密级：内部 / 密级：秘密
    r"^(内部|秘密|机密|公开|受控|非受控)$",# 单独的密级词
    r"版本[：:]\s*[A-Za-z]",              # 版本：C
    r"Rev\.[A-Za-z]",                      # Rev.A
    r"第\s*\d+\s*页",                      # 第1页
    r"共\s*\d+\s*页",                      # 共X页
    r"\d{4}[-年]\d{1,2}[-月]\d{0,2}",     # 日期
    r"^(编制|审核|批准|校对|会签)[：:]",   # 签署栏
    r"^(发布|实施)[：:]",
    r"^(发布日期|实施日期)[：:]",
    r"中国商用飞机有限责任公司",            # 公司名（封面最顶部）
    r"中国航空",
    r"上海飞机",
    r"^CPS\d+",                            # 文档编号行
    r"^HB\d+",
    r"^Q/\w+",
    r"^[\d\.\-\s]+$",                      # 纯数字/分隔符行
]

_BLACKLIST_RE = [re.compile(p) for p in TITLE_BLACKLIST]


def _is_blacklisted(text: str) -> bool:
    t = text.strip()
    return any(rx.search(t) for rx in _BLACKLIST_RE)


def extract_title_from_first_page(pdf_path: Path) -> str:
    """
    基于字号优先策略提取首页标题：
    1. 用 pdfplumber extract_words 获取每个词的字体大小
    2. 过滤黑名单词条
    3. 找出最大字号的一组词并合并
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            words = pdf.pages[0].extract_words(extra_attrs=["fontname", "size"])
    except Exception:
        return ""

    # 过滤掉 size 缺失 / 为 0 的词，以及黑名单词
    clean_words = [
        w for w in words
        if w.get("size") and w["size"] > 0 and not _is_blacklisted(w["text"])
    ]

    if not clean_words:
        return ""

    max_size = max(w["size"] for w in clean_words)

    # 收集所有最大字号的词（允许 ±0.5pt 误差，兼容同行微小浮点差异）
    title_words = [w for w in clean_words if abs(w["size"] - max_size) <= 0.5]

    # 按从上到下、从左到右排序
    title_words.sort(key=lambda w: (round(w["top"]), w["x0"]))

    # 合并同一行的词（行间插换行，行内加空格）
    lines: list[list[str]] = []
    current_row: int | None = None
    for w in title_words:
        row = round(w["top"])
        if current_row is None or abs(row - current_row) > 2:
            lines.append([w["text"]])
            current_row = row
        else:
            lines[-1].append(w["text"])

    title = " ".join("".join(line) for line in lines).strip()
    return title


def extract_meta(pdf_path: Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        cover_text = pdf.pages[0].extract_text() or ""

    # ── 文档编号 & 版本 ────────────────────────────────────────────────────
    # 更宽松：支持 "CPS0215版本:A" 和 "CPS0215 版本: A" 两种格式
    doc_match = re.search(r'(CPS\d+)\s*版本[:：]\s*([A-Z])', cover_text)

    if not doc_match:
        name_match = re.search(r'(CPS\d+)', pdf_path.stem)
        doc_id  = name_match.group(1) if name_match else ""
        version = ""
    else:
        doc_id  = doc_match.group(1)
        version = doc_match.group(2)

    # ── 标题（三级优先）─────────────────────────────────────────────────────
    # 方法1：字号优先 —— 找首页字号最大的非干扰词组
    title = extract_title_from_first_page(pdf_path)

    # 方法2：正则匹配"中国商用飞机有限责任公司(规范|文件)\n标题\n"
    if not title:
        title_match = re.search(
            r'中国商用飞机有限责任公司(?:规范|文件)\n(.*?)\n',
            cover_text
        )
        if title_match:
            title = title_match.group(1).strip()

    # 方法3：原有行扫描 + 文件名 fallback
    if not title:
        title = _extract_title_fallback(cover_text, pdf_path)

    # ── 日期 ───────────────────────────────────────────────────────────────
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', cover_text)
    issue_date = date_match.group(1) if date_match else ""

    return {
        "doc_id":     doc_id,
        "version":    version,
        "title":      title,
        "issue_date": issue_date,
    }
def extract_sections(pdf_path: Path, doc_id: str) -> list[dict]:
    """
    逐行扫描 PDF 提取章节及其 BBox。
    不再合并全文，以保留精准的坐标信息。
    """
    sections = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # 1. 遍历所有页，提取所有符合 SECTION_PATTERN 的行及其坐标
            all_lines = []
            for page_idx, page in enumerate(pdf.pages):
                words = page.extract_words()
                # 按行合并单词
                lines_in_page = []
                if not words: continue
                
                # 简单聚类：根据 top 坐标合并单词为行
                words.sort(key=lambda w: (w["top"], w["x0"]))
                curr_line = [words[0]]
                for w in words[1:]:
                    if abs(w["top"] - curr_line[-1]["top"]) < 3: # 同一行
                        curr_line.append(w)
                    else:
                        lines_in_page.append(curr_line)
                        curr_line = [w]
                lines_in_page.append(curr_line)

                def _line_to_text(words_in_line: list[dict]) -> str:
                    # 按 x0 重新排序，确保行内单词是视觉左→右顺序
                    # （PDF 某些字体的 top 基线偏差可能导致编号与标题顺序颠倒）
                    ordered_words = sorted(words_in_line, key=lambda w: w["x0"])
                    raw_text = " ".join(w["text"] for w in ordered_words).strip()
                    return fix_token_spacing(raw_text)

                page_line_texts = [_line_to_text(line) for line in lines_in_page]
                page_is_toc = _is_likely_toc_page(page_line_texts)

                line_idx = 0
                while line_idx < len(lines_in_page):
                    line_words = lines_in_page[line_idx]
                    text = _normalize_heading_candidate(
                        page_line_texts[line_idx],
                        page_is_toc,
                    )
                    heading = _match_section_heading(text)
                    consumed_lines = 1
                    bbox_words = line_words

                    if heading and line_idx + 1 < len(lines_in_page):
                        next_words = lines_in_page[line_idx + 1]
                        next_text = _normalize_heading_candidate(
                            page_line_texts[line_idx + 1],
                            page_is_toc,
                        )
                        merged_heading = _merge_wrapped_heading(text, next_text)
                        if merged_heading:
                            heading = merged_heading
                            consumed_lines = 2
                            bbox_words = sorted(line_words + next_words, key=lambda w: (w["top"], w["x0"]))

                    if heading and is_likely_section_title(heading[0], heading[1]):
                        # 这是一个章节标题行
                        all_lines.append({
                            "type": "heading",
                            "number": heading[0],
                            "title": heading[1],
                            "page_idx": page_idx,
                            "bbox": [
                                min(w["x0"] for w in bbox_words),
                                min(w["top"] for w in bbox_words),
                                max(w["x1"] for w in bbox_words),
                                max(w["bottom"] for w in bbox_words),
                            ],
                            "global_pos": len(all_lines)
                        })
                    else:
                        all_lines.append({
                            "type": "text",
                            "content": text,
                            "page_idx": page_idx
                        })
                    line_idx += consumed_lines

            # 2. 根据标题边界切分正文
            headings = [line for line in all_lines if line["type"] == "heading"]
            # 过滤干扰项（同原有逻辑）
            headings = [h for h in headings
                       if len(h["title"].strip()) >= 2
                       and h["title"].strip() != '_'
                       and not h["title"].strip().replace('.', '').replace(' ', '').isdigit()]
            # first-wins 去重：同一 number 只保留第一次出现（TOC 先于正文，正文先于尾部重复）
            _seen_nums: set[str] = set()
            _deduped: list[dict] = []
            for h in headings:
                if h["number"] not in _seen_nums:
                    _seen_nums.add(h["number"])
                    _deduped.append(h)
            headings = _deduped
            headings = _trim_front_matter_headings(headings)

            for i, h in enumerate(headings):
                # 收集当前标题到下一个标题之间的所有文本
                start_idx = h["global_pos"]
                end_idx = headings[i+1]["global_pos"] if i+1 < len(headings) else len(all_lines)
                
                content_parts = []
                for j in range(start_idx, end_idx):
                    line = all_lines[j]
                    if line["type"] == "text":
                        content_parts.append(line["content"])
                    elif line["type"] == "heading" and j == start_idx:
                        # 标题行本身也包含标题文本
                        content_parts.append(f"{line['number']} {line['title']}")
                
                raw_content = "\n".join(content_parts)
                safe_num = h["number"].replace(".", "_")
                sections.append({
                    "chunk_id":  f"{doc_id}_{safe_num}",
                    "number":    h["number"],
                    "title":     h["title"],
                    "content":   clean_content(raw_content),
                    "level":     len(h["number"].split(".")),
                    "seq_index": i,
                    "page_idx":  h["page_idx"],
                    "bbox":      h["bbox"],
                })

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("提取章节坐标失败: %s", e)
        return _extract_sections_legacy(pdf_path, doc_id)

    if not sections:
        return _extract_sections_legacy(pdf_path, doc_id)

    return sections

def _extract_sections_legacy(pdf_path: Path, doc_id: str) -> list[dict]:
    # 原有的合并全文再正则匹配的逻辑，作为 Fallback
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            page_lines = [
                fix_token_spacing(line.strip())
                for line in page_text.split('\n')
                if line.strip()
            ]
            page_is_toc = _is_likely_toc_page(page_lines)
            normalized_lines = [
                _normalize_heading_candidate(line, page_is_toc)
                for line in page_lines
            ]
            full_text += "\n".join(normalized_lines) + "\n"

    # 多模式匹配：收集所有匹配并去重（按 start 排序）
    all_matches: list[tuple[int, re.Match]] = []
    seen_starts: set[int] = set()
    for pat in SECTION_PATTERNS:
        for m in pat.finditer(full_text):
            if m.start() not in seen_starts:
                seen_starts.add(m.start())
                all_matches.append((m.start(), m))
    all_matches.sort(key=lambda x: x[0])

    matches = [
        m for _, m in all_matches
        if len(m.group(2).strip()) >= 2
        and m.group(2).strip() != '_'
        and not m.group(2).strip().replace('.', '').replace(' ', '').isdigit()
        and is_likely_section_title(m.group(1), m.group(2).strip())
    ]

    # first-wins 去重：同一 number 只保留第一次出现
    seen_numbers: set[str] = set()
    deduped_matches = []
    for m in matches:
        n = m.group(1)
        if n not in seen_numbers:
            seen_numbers.add(n)
            deduped_matches.append(m)
    matches = deduped_matches
    matches = _trim_front_matter_headings([
        {"number": m.group(1), "title": m.group(2).strip(), "_match": m}
        for m in matches
    ])
    matches = [item["_match"] for item in matches]

    sections = []
    for i, match in enumerate(matches):
        number = match.group(1)
        title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        content = clean_content(full_text[start: end])
        safe_num = number.replace(".", "_")
        sections.append({
            "chunk_id":  f"{doc_id}_{safe_num}",
            "number":    number,
            "title":     title,
            "content":   content,
            "level":     len(number.split(".")),
            "seq_index": i,
        })
    return sections

def _rows_to_markdown(rows: list[list[str]]) -> str:
    """将二维列表转为 Markdown 表格字符串。"""
    if not rows:
        return ""
    # 规整化：确保每行列数一致
    width = max(len(r) for r in rows)
    rows  = [(r + [""] * (width - len(r)))[:width] for r in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    sep    = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body   = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows[1:])
    return f"{header}\n{sep}\n{body}" if body else f"{header}\n{sep}"


def extract_tables_pdfplumber(pdf_path: Path, doc_id: str, sections: list[dict]) -> list[dict]:
    """
    用 pdfplumber 提取 PDF 中的表格，转为 Markdown。
    每个表格关联到最近的 Section（按页码从后向前查找）。
    返回格式与 entity_writer.write_tables() 兼容。
    """
    import json as _json

    # 建立 page_idx → chunk_id 的映射（每页取第一个 section）
    page_to_chunk: dict[int, str] = {}
    for s in sections:
        pi = s.get("page_idx")
        if pi is not None and pi not in page_to_chunk:
            page_to_chunk[pi] = s["chunk_id"]
    fallback_chunk = sections[0]["chunk_id"] if sections else f"{doc_id}_1"

    tables: list[dict] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            table_seq = 0
            for page_idx, page in enumerate(pdf.pages):
                raw_tables = page.extract_tables() or []
                for tbl in raw_tables:
                    if not tbl:
                        continue
                    # 过滤空行，规整化单元格
                    rows = [[str(cell or "").strip() for cell in row] for row in tbl]
                    rows = [r for r in rows if any(c for c in r)]
                    if len(rows) < 2:  # 少于 2 行（含表头）无意义
                        continue

                    markdown = _rows_to_markdown(rows)
                    rows_json = _json.dumps(rows, ensure_ascii=False)

                    # 查找最近的章节：同页 → 前一页 → ... → fallback
                    chunk_id = page_to_chunk.get(page_idx)
                    if chunk_id is None:
                        for pi in range(page_idx - 1, -1, -1):
                            if pi in page_to_chunk:
                                chunk_id = page_to_chunk[pi]
                                break
                    chunk_id = chunk_id or fallback_chunk

                    tables.append({
                        "table_id":    f"{doc_id}_tbl_{table_seq}",
                        "chunk_id":    chunk_id,
                        "markdown":    markdown,
                        "rows_json":   rows_json,
                        "page_index":  page_idx,
                        "row_count":   max(0, len(rows) - 1),
                        "bbox":        tbl.bbox,  # 新增：保存表格在 PDF 页面上的坐标 [x0, top, x1, bottom]
                        "constraints": [],
                    })
                    table_seq += 1
    except Exception as e:
        logger.warning("pdfplumber 表格提取失败 %s: %s", pdf_path.name, e)

    return tables


def parse(file_path: "Path | str") -> "DocumentSchema":
    """解析文档，按扩展名路由到对应解析器。

    对于 .doc/.docx 文件，LibreOffice 转换后的临时 PDF 路径会存入
    doc.pdf_path，供调用方提取图片/表格后自行清理。
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".doc", ".docx"):
        pdf_path = _convert_office_to_pdf(path)
        doc = _parse_pdf(pdf_path, fallback_doc_id=_extract_doc_id_from_filename(path))
        # 保留 pdf_path，让调用方用于图片/表格提取，调用方负责清理
        doc.pdf_path = pdf_path
        return doc

    return _parse_pdf(path)


def _parse_pdf(pdf_path: Path, fallback_doc_id: str = "") -> "DocumentSchema":
    """从 PDF 文件提取元数据、章节和引用。"""
    try:
        from .ocr_engine import is_available as ocr_available, pdf_has_scanned_pages
        if ocr_available() and pdf_has_scanned_pages(str(pdf_path)):
            from .ocr_parser import parse_with_ocr
            return parse_with_ocr(pdf_path)
    except Exception as e:
        logger.warning("OCR 路由失败，降级到标准解析: %s", e)

    meta = extract_meta(pdf_path)
    if not meta["doc_id"]:
        if fallback_doc_id:
            meta["doc_id"] = fallback_doc_id
        else:
            raise ValueError(
                f"无法提取文档编号（封面和文件名均无法识别）: {pdf_path.name}"
            )

    sections = extract_sections(pdf_path, meta["doc_id"])
    refs = extract_refs(sections)

    return DocumentSchema(
        doc_id=meta["doc_id"],
        version=meta["version"],
        title=meta["title"],
        issue_date=meta["issue_date"],
        total_sections=len(sections),
        sections=[SectionSchema(**s) for s in sections],
        refs=refs,
        pdf_path=pdf_path,
    )


def _convert_office_to_pdf(office_path: Path) -> Path:
    """用 LibreOffice 将 .doc/.docx 直接转换为 PDF（输出到 /tmp）。"""
    import os as _os
    import subprocess as _subprocess

    fmt = _detect_doc_format(office_path)
    if fmt == "visio":
        raise ValueError(
            f"文件 {office_path.name} 是 Visio 绘图文件，无法解析为文档章节。"
        )

    soffice = _find_soffice()
    if not soffice:
        raise RuntimeError(
            "未找到 LibreOffice — 请安装后重启服务，或将文件转换为 PDF 后上传。"
        )

    output_dir = Path("/tmp")
    pdf_path = output_dir / (office_path.stem + ".pdf")

    env = _os.environ.copy()
    env["HOME"] = "/tmp"

    result = _subprocess.run(
        [soffice, "--headless", "--norestore",
         "--convert-to", "pdf",
         "--outdir", str(output_dir),
         str(office_path)],
        capture_output=True, text=True, timeout=180, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转 PDF 失败 (exit {result.returncode}): {result.stderr}")
    if not pdf_path.exists():
        raise RuntimeError(f"转换后 PDF 不存在: {pdf_path}")

    logger.info("LibreOffice 转换完成: %s -> %s (%.1f MB)",
                office_path.name, pdf_path.name, pdf_path.stat().st_size / 1024 / 1024)
    return pdf_path


def _extract_doc_id_from_filename(path: Path) -> str:
    m = re.search(r'(CPS\d+)', path.name, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _find_soffice() -> str | None:
    """
    Locate a working soffice/LibreOffice binary on Linux (Docker) or macOS.
    Verifies each candidate via --version to skip broken wrapper scripts.
    """
    import os as _os
    import shutil as _shutil
    import subprocess as _subprocess
    import glob as _glob

    def _works(path: str) -> bool:
        if not (_os.path.isfile(path) and _os.access(path, _os.X_OK)):
            return False
        try:
            r = _subprocess.run(
                [path, "--version"],
                stdout=_subprocess.PIPE,
                stderr=_subprocess.PIPE,
                timeout=8,
            )
            return r.returncode == 0
        except Exception:
            return False

    candidates = [
        # Linux (apt-installed)
        "/usr/bin/soffice",
        "/usr/lib/libreoffice/program/soffice",
        # macOS app bundle paths
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/Applications/LibreOffice 7.app/Contents/MacOS/soffice",
        "/Applications/LibreOffice 24.app/Contents/MacOS/soffice",
        _os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        *_glob.glob("/usr/local/Caskroom/libreoffice/*/LibreOffice.app/Contents/MacOS/soffice"),
        *_glob.glob("/opt/homebrew/Caskroom/libreoffice/*/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    for p in candidates:
        if _works(p):
            return p

    # Fall back to PATH
    for name in ("soffice", "libreoffice"):
        found = _shutil.which(name)
        if found and _works(found):
            return found

    return None


def _detect_doc_format(path: Path) -> str:
    """
    检测文件的实际格式。
    返回值:
      'visio'      — 真正的 Visio OOXML 文件（ZIP 根目录有 visio/ 文件夹）
      'docx'       — 已经是 OOXML Word 文档（含 word/document.xml）
      'doc_binary' — 旧版 OLE/CFB 二进制 .doc，需要 LibreOffice 转换
    注意：不能用 [Content_Types].xml 或 drs/e2oDoc.xml 判断，因为 Word .doc
    文件中嵌入的 Visio OLE 对象会让 zipfile 读到 embedded ZIP，含有 drs/ 内容，
    但那是嵌入对象，不是文件本身的格式。
    """
    try:
        import zipfile as _zf
        with _zf.ZipFile(path) as z:
            names = z.namelist()
            # 真正的 Visio OOXML：根目录有 visio/ 文件夹
            if any(n.startswith("visio/") for n in names):
                return "visio"
            # 正常 DOCX
            if "word/document.xml" in names:
                return "docx"
    except Exception:
        pass
    # 旧版二进制 OLE/CFB .doc — 需要 LibreOffice 转换
    return "doc_binary"


def _validate_converted_docx(converted: Path) -> None:
    """验证转换后的 docx 是否包含有效 Word 内容，无效则抛出 ValueError"""
    import zipfile as _zf
    try:
        with _zf.ZipFile(converted) as z:
            names = z.namelist()
            if "word/document.xml" not in names:
                raise ValueError(
                    f"转换后文件不含 word/document.xml（实际内容: {names[:6]}），"
                    "原文件可能是 Visio 绘图或其他非 Word 格式。"
                )
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            # 检查是否有实质性文本内容（非空文档）
            import re as _re
            text_content = _re.sub(r"<[^>]+>", "", xml)
            if len(text_content.strip()) < 50:
                raise ValueError("转换后文档内容为空，原文件可能是纯绘图文件，无法提取文本。")
    except _zf.BadZipFile:
        raise ValueError("转换后文件不是有效的 ZIP/DOCX 格式。")


def _convert_doc_to_docx(path: Path) -> Path:
    """将 .doc（旧版 OLE 二进制）转换为 .docx，使用 LibreOffice。"""
    import os as _os
    import subprocess as _subprocess

    # ── 预检：拒绝非 Word 格式（Visio 等）────────────────────────────────────────
    fmt = _detect_doc_format(path)
    if fmt == "docx":
        # 已经是 DOCX，无需转换
        return path
    if fmt == "visio":
        raise ValueError(
            f"文件 {path.name} 是 Microsoft Visio 绘图文件，不是 Word 文档，无法解析章节内容。"
            "如需处理，请将 Visio 文件转换为 PDF 后单独上传。"
        )

    soffice = _find_soffice()
    if not soffice:
        raise ValueError(
            "DOC 转换失败：服务器未安装 LibreOffice。"
            "请将文件另存为 .docx 格式后重新上传，或联系管理员安装 LibreOffice。"
        )

    out_dir = path.parent / "_converted"
    out_dir.mkdir(exist_ok=True)
    converted = out_dir / f"{path.stem}.docx"

    env = _os.environ.copy()
    env["HOME"] = "/tmp"  # LibreOffice 在 Docker 中无法写入默认 HOME，需要可写目录

    cmd = [
        soffice, "--headless", "--norestore",
        "--convert-to", "docx:MS Word 2007 XML",
        "--outdir", str(out_dir), str(path),
    ]
    result = _subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转换失败 (exit {result.returncode}): {result.stderr}")
    if not converted.exists():
        raise RuntimeError(f"LibreOffice 转换后文件不存在: {converted}")

    _validate_converted_docx(converted)
    return converted
