"""
fix_titles.py — 批量修复 Neo4j 中已入库文档的错误标题

背景：
  旧版 parser.py 会将封面的"密级：内部"等干扰行误识别为标题。
  新版 parser.py 已修复（字号优先策略）。
  本脚本对 Neo4j 中所有 Document 节点重新提取标题并写回。

逻辑：
  1. 从 Neo4j 查询所有 Document 节点（name, title）
  2. 在 uploads/ 目录下按 doc_id 前缀匹配对应 PDF
  3. 用修复后的 extract_meta() 重新提取标题
  4. 仅更新"有变化"的节点（新旧不同，或旧值为 None/空）
  5. 打印每条变更，最终输出汇总

用法：
  cd backend
  python scripts/fix_titles.py                         # 默认 uploads/
  python scripts/fix_titles.py /path/to/pdf/folder    # 指定目录
  python scripts/fix_titles.py --dry-run              # 只预览，不写库
"""
import sys
import argparse
from pathlib import Path

# ── 路径配置 ──────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from neo4j import GraphDatabase
from src.services.parser import extract_meta

# ── Neo4j 连接（从 .env 读取，若读取失败则用默认值）──────────────────────────
def _load_env() -> dict:
    env: dict = {}
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        env_file = BACKEND_DIR.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

_env = _load_env()
NEO4J_URI      = _env.get("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = _env.get("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = _env.get("NEO4J_PASSWORD", "neo4j")


def get_all_documents(session) -> list[dict]:
    """返回 Neo4j 中所有 Document 节点的 name（=doc_id）和 title。"""
    result = session.run(
        "MATCH (d:Document) RETURN d.name AS doc_id, d.title AS title ORDER BY d.name"
    )
    return [{"doc_id": r["doc_id"], "title": r["title"]} for r in result]


def find_pdf(doc_id: str, pdf_dir: Path) -> Path | None:
    """在 pdf_dir 下找到匹配 doc_id 的第一个 PDF 文件。
    文件名格式：CPS1002_J_整体油箱的密封_422413.pdf
    """
    # 精确前缀匹配（大小写不敏感）
    candidates = list(pdf_dir.glob(f"{doc_id}_*.pdf"))
    if not candidates:
        candidates = list(pdf_dir.glob(f"{doc_id.lower()}_*.pdf"))
    return candidates[0] if candidates else None


def needs_update(old_title: str | None, new_title: str) -> bool:
    """判断是否需要更新：旧值为空/None，或与新值不同。"""
    if not old_title:
        return bool(new_title)
    return new_title and new_title != old_title


def update_title(session, doc_id: str, new_title: str) -> None:
    session.run(
        "MATCH (d:Document {name: $doc_id}) SET d.title = $title",
        doc_id=doc_id,
        title=new_title,
    )


def main():
    parser = argparse.ArgumentParser(description="批量修复 Neo4j 文档标题")
    parser.add_argument("pdf_dir", nargs="?", default=None,
                        help="PDF 目录（默认：backend/uploads/）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只预览变更，不实际写入 Neo4j")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else BACKEND_DIR / "uploads"
    dry_run = args.dry_run

    if not pdf_dir.is_dir():
        print(f"[错误] PDF 目录不存在：{pdf_dir}")
        sys.exit(1)

    print(f"PDF 目录：{pdf_dir}")
    print(f"Neo4j  ：{NEO4J_URI}")
    print(f"模式   ：{'预览（dry-run）' if dry_run else '写入'}")
    print("=" * 70)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    updated   = 0
    skipped   = 0
    no_pdf    = 0
    errors    = 0

    try:
        with driver.session() as session:
            docs = get_all_documents(session)
            print(f"共 {len(docs)} 个 Document 节点\n")

            for doc in docs:
                doc_id    = doc["doc_id"]
                old_title = doc["title"]

                pdf_path = find_pdf(doc_id, pdf_dir)
                if not pdf_path:
                    print(f"  [跳过] {doc_id:<12}  无匹配 PDF（存根节点）")
                    no_pdf += 1
                    continue

                try:
                    meta      = extract_meta(pdf_path)
                    new_title = meta.get("title", "").strip()
                except Exception as e:
                    print(f"  [错误] {doc_id:<12}  解析失败: {e}")
                    errors += 1
                    continue

                if not needs_update(old_title, new_title):
                    print(f"  [无变化] {doc_id:<12}  {repr(old_title)}")
                    skipped += 1
                    continue

                # 有变化 — 打印并（非 dry-run 时）写入
                change_type = "修复" if old_title else "补全"
                print(
                    f"  [{change_type}] {doc_id:<12}  "
                    f"{repr(old_title):30s}  →  {repr(new_title)}"
                )

                if not dry_run:
                    update_title(session, doc_id, new_title)
                updated += 1

    finally:
        driver.close()

    print()
    print("=" * 70)
    print(f"完成：修复/补全 {updated} 条，无变化 {skipped} 条，"
          f"无 PDF {no_pdf} 条，错误 {errors} 条"
          + ("（dry-run，未实际写入）" if dry_run else "，已写入 Neo4j"))


if __name__ == "__main__":
    main()
