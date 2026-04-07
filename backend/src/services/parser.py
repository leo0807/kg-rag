import re
import pdfplumber
from pathlib import Path
from ..models.schemas import DocumentSchema, SectionSchema

SECTION_PATTERN = re.compile(
    r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s+([\u4e00-\u9fff\w\/\-]+)$',
    re.MULTILINE
)

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
    # 提取所有章节，每个章节包含章节号、标题、正文内容
    # 第一步：把所有页的文字合并成一个字符串
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"

    # 第二步：找到所有章节的位置
    matches = list(SECTION_PATTERN.finditer(full_text))
    matches = [m for m in matches if (len(m.group(2))) >= 2 and m.group(2) != '_']

    # 第三步：按章节边界切分内容
    sections = []
    for i, match in enumerate(matches):
        number = match.group(1)
        title = match.group(2)

        # 内容从本章节标题开始
        start = match.start()
        # 内容到下一章节标题结束，最后一章到文档末尾
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)

        content = clean_content(full_text[start: end])

        sections.append({
            "chunk_id": f"{doc_id}_{number}",
            "number": number,
            "title": title,
            "content": content,
        })

    return sections

def parse(pdf_path: Path) -> dict:
    # 解析整个 PDF，返回元数据 + 所有章节
    meta = extract_meta(pdf_path)
    sections = extract_sections(pdf_path, meta["doc_id"])
    refs = extract_refs(sections)

    # ** 是字典解包，把一个字典的所有键值对展开到另一个字典里：
    if not meta["doc_id"]:
        raise ValueError(
            f"无法提取文档编号（封面和文件名均无法识别）: {pdf_path.name}"
        )

    return DocumentSchema(
        doc_id=meta["doc_id"],
        version=meta["version"],
        title=meta["title"],
        issue_date=meta["issue_date"],
        total_sections=len(sections),
        sections=[SectionSchema(**s) for s in sections],
        refs=refs,
    )