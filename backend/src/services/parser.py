import re
import pdfplumber
from pathlib import Path

import re
import pdfplumber
from pathlib import Path

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