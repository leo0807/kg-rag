import re
import pdfplumber
from pathlib import Path

import re
import pdfplumber
from pathlib import Path

SECTION_PATTERN = re.compile(
    r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s+([\u4e00-\u9fff\w\/\-]+)$',
    re.MULTILINE
)

def extract_meta(pdf_path: Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        cover_text = pdf.pages[0].extract_text() or ""

    # 提取规范编号和版本
    doc_match = re.search(r'(CPS\d+)版本[:：]([A-Z])', cover_text)
    doc_id  = doc_match.group(1) if doc_match else ""
    version = doc_match.group(2) if doc_match else ""

    # 提取标题（在"规范"和发布日期之间的那行）
    title_match = re.search(
        r'中国商用飞机有限责任公司规范\n(.*?)\n',
        cover_text
    )
    title = title_match.group(1).strip() if title_match else ""

    # 提取发布日期
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})发布', cover_text)
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

        content = full_text[start: end].strip()

        sections.append({
            "chunk_id": f"{doc_id}_{number}",
            "number": number,
            "title": title,
            "content": content[:500]# 先截断500字，避免输出太长
        })

    return sections