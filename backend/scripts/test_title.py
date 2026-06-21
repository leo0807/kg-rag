"""
test_title.py — 批量验证首页标题识别结果

用法：
    cd backend
    python scripts/test_title.py                        # 默认扫描 uploads/
    python scripts/test_title.py /path/to/pdf/folder   # 指定目录
"""
import sys
from pathlib import Path

# 加入 backend/ 到 sys.path，使相对导入可以工作
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.parsing.parser_meta import extract_meta, extract_title_from_first_page

def main():
    pdf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[1] / "uploads"

    pdfs = sorted(pdf_dir.glob("*.pdf"))[:20]
    if not pdfs:
        print(f"[!] 未找到 PDF 文件：{pdf_dir}")
        return

    print(f"{'文件名':<55} {'字号方法':<30} {'最终标题'}")
    print("-" * 115)

    for pdf in pdfs:
        # 单独调用字号方法，方便对比
        font_title = extract_title_from_first_page(pdf)
        meta       = extract_meta(pdf)
        final      = meta.get("title", "未识别")
        mark       = " ✓" if final and final == font_title else (" ↩" if final else " ✗")
        print(f"{pdf.name:<55} {(font_title or '—'):<30} {final}{mark}")

if __name__ == "__main__":
    main()
