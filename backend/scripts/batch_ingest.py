"""
scripts/batch_ingest.py
批量导入 PDF 脚本

用法：
    python scripts/batch_ingest.py --dir /path/to/pdf/folder
    python scripts/batch_ingest.py --dir /path/to/pdf/folder --skip-existing
"""
import argparse
import json
import sys
import time
from pathlib import Path

# 把 backend/ 加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import init_db
from src.core.logging import setup_logging
from src.services.parser import parse
from src.services.neo4j_writer import write_document

PROGRESS_FILE = Path("ingest_progress.json")


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed": [], "failed": {}}


def save_progress(p: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(p, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="批量导入 CPS PDF 文件")
    parser.add_argument("--dir",           required=True, help="PDF 文件夹路径")
    parser.add_argument("--skip-existing", action="store_true", help="跳过已入库文件")
    parser.add_argument("--limit",         type=int, default=0, help="最多处理几个文件，0=全部")
    args = parser.parse_args()

    setup_logging()
    init_db()

    pdf_dir = Path(args.dir)
    if not pdf_dir.exists():
        print(f"错误：目录不存在 {pdf_dir}")
        sys.exit(1)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"错误：目录下没有 PDF 文件 {pdf_dir}")
        sys.exit(1)

    if args.limit:
        pdf_files = pdf_files[:args.limit]

    progress  = load_progress()
    total     = len(pdf_files)
    succeeded = 0
    failed    = 0
    skipped   = 0

    print(f"\n找到 {total} 个 PDF 文件\n{'─' * 50}")

    for i, pdf_path in enumerate(pdf_files, start=1):
        file_key = pdf_path.name
        prefix   = f"[{i:3d}/{total}]"

        # 跳过已处理
        if args.skip_existing and file_key in progress["completed"]:
            print(f"{prefix} 跳过（已入库）{pdf_path.name}")
            skipped += 1
            continue

        print(f"{prefix} 处理中 {pdf_path.name} ...", end=" ", flush=True)
        start = time.time()

        try:
            doc = parse(pdf_path)
            write_document(doc)
            elapsed = time.time() - start

            progress["completed"].append(file_key)
            progress["failed"].pop(file_key, None)
            save_progress(progress)

            print(f"✓ {doc.doc_id} ({len(doc.sections)} 章节) {elapsed:.1f}s")
            succeeded += 1

        except Exception as e:
            elapsed = time.time() - start
            progress["failed"][file_key] = str(e)
            save_progress(progress)
            print(f"✗ 失败: {e} {elapsed:.1f}s")
            failed += 1

    print(f"\n{'─' * 50}")
    print(f"完成：成功 {succeeded}，失败 {failed}，跳过 {skipped}，共 {total}")


if __name__ == "__main__":
    main()