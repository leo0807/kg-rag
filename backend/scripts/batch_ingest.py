"""
scripts/batch_ingest.py
批量导入 PDF 脚本

用法：
    python scripts/batch_ingest.py --dir /path/to/pdf/folder
    python scripts/batch_ingest.py --dir /path/to/pdf/folder --skip-existing
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

# 把 backend/ 加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import init_db, get_driver
from src.core.logging import setup_logging
from src.services.parser import parse
from src.services.neo4j_writer import write_document

logger = logging.getLogger(__name__)


def _extract_and_store_images(pdf_path: Path, doc_id: str, sections: list) -> int:
    """
    从 PDF 中提取嵌入图片，上传到 MinIO，并在 Neo4j 中创建 :Image 节点。
    图片归属到页码最近的 Section（page_idx <= 图片页码的最后一个章节）。
    单张图片失败不影响整体流程，记录日志后跳过。
    返回成功写入的图片数量。
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        logger.warning("pymupdf 未安装，跳过图片提取")
        return 0

    # 构建页码 → chunk_id 的映射（取每页上最后一个 section）
    page_to_chunk: dict[int, str] = {}
    for s in sections:
        if s.page_idx is not None:
            page_to_chunk[s.page_idx] = s.chunk_id

    sorted_pages = sorted(page_to_chunk.keys())

    def find_section_for_page(page_num: int) -> str | None:
        """返回 page_idx <= page_num 的最后一个章节 chunk_id"""
        best = None
        for p in sorted_pages:
            if p <= page_num:
                best = page_to_chunk[p]
            else:
                break
        return best

    try:
        from src.core.storage import upload_bytes, BUCKET_EXTRACTED_IMAGES
        storage_ok = True
    except Exception as e:
        logger.warning("MinIO 存储模块加载失败，图片不会上传到 MinIO: %s", e)
        storage_ok = False

    local_image_dir = Path("uploads/images")
    local_image_dir.mkdir(parents=True, exist_ok=True)

    driver = get_driver()
    doc = fitz.open(str(pdf_path))
    image_nodes: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                width  = base_image["width"]
                height = base_image["height"]

                # 过滤装饰性小图
                if width < 100 or height < 100:
                    continue

                ext       = base_image["ext"] or "png"
                img_bytes = base_image["image"]
                image_id  = f"{doc_id}_page{page_num + 1}_img{img_idx}"
                minio_key = f"{doc_id}/{page_num + 1}_{img_idx}.{ext}"

                # 保存到本地（供 VLM 分析使用）
                local_path = local_image_dir / f"{image_id}.{ext}"
                try:
                    local_path.write_bytes(img_bytes)
                except Exception as e:
                    logger.warning("图片本地保存失败 %s: %s", image_id, e)
                    local_path = None

                # 上传到 MinIO
                minio_path = ""
                if storage_ok:
                    try:
                        upload_bytes(
                            BUCKET_EXTRACTED_IMAGES,
                            minio_key,
                            img_bytes,
                            content_type=f"image/{ext}",
                        )
                        minio_path = minio_key
                    except Exception as e:
                        logger.warning("图片上传 MinIO 失败 %s: %s", image_id, e)

                chunk_id = find_section_for_page(page_num)
                image_nodes.append({
                    "image_id":   image_id,
                    "doc_id":     doc_id,
                    "page_num":   page_num + 1,
                    "path":       str(local_path) if local_path else "",
                    "minio_path": minio_path,
                    "is_drawing": False,
                    "chunk_id":   chunk_id,  # 归属章节，可为 None
                })

            except Exception as e:
                logger.warning(
                    "提取图片失败 doc=%s page=%d img=%d: %s",
                    doc_id, page_num + 1, img_idx, e,
                )

    doc.close()

    if not image_nodes:
        return 0

    # 批量写入 Neo4j Image 节点
    try:
        with driver.session() as session:
            # 写入 Image 节点并挂到 Document
            session.run("""
                UNWIND $images AS img
                MATCH (d:Document {name: img.doc_id})
                MERGE (i:Image {image_id: img.image_id})
                SET i.doc_id     = img.doc_id,
                    i.page_num   = img.page_num,
                    i.path       = img.path,
                    i.minio_path = img.minio_path,
                    i.is_drawing = img.is_drawing
                MERGE (d)-[:HAS_IMAGE]->(i)
            """, images=image_nodes)

            # 建立 (Section)-[:HAS_IMAGE]->(Image) 关系（有归属章节的图片）
            section_links = [n for n in image_nodes if n.get("chunk_id")]
            if section_links:
                session.run("""
                    UNWIND $links AS lnk
                    MATCH (s:Section {chunk_id: lnk.chunk_id})
                    MATCH (i:Image   {image_id: lnk.image_id})
                    MERGE (s)-[:HAS_IMAGE]->(i)
                """, links=section_links)

        logger.info("写入 %d 张图片 doc_id=%s", len(image_nodes), doc_id)
        return len(image_nodes)

    except Exception as e:
        logger.warning("Neo4j Image 节点写入失败 doc_id=%s: %s", doc_id, e)
        return 0

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

    # 初始化 Milvus 和 ES
    try:
        from src.services.milvus_store import connect_milvus
        from src.services.es_store import init_es_index
        from src.core.config import settings
        
        connect_milvus(host=settings.MILVUS_HOST, port=str(settings.MILVUS_PORT))
        init_es_index()
    except Exception as e:
        print(f"警告：Milvus/ES 初始化失败，后续写入可能会报错: {e}")

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
    # 转换为 set 提高查找效率
    completed_set = set(progress.get("completed", []))
    
    total     = len(pdf_files)
    succeeded = 0
    failed    = 0
    skipped   = 0

    print(f"\n找到 {total} 个 PDF 文件\n{'─' * 50}")

    for i, pdf_path in enumerate(pdf_files, start=1):
        file_key = pdf_path.name
        prefix   = f"[{i:3d}/{total}]"

        # 跳过已处理
        if file_key in completed_set:
            if args.skip_existing:
                print(f"{prefix} 跳过（已入库）{pdf_path.name}")
                skipped += 1
                continue
            else:
                print(f"{prefix} 警告：{pdf_path.name} 已在记录中，将重新处理并覆盖")

        print(f"{prefix} 处理中 {pdf_path.name} ...", end=" ", flush=True)
        start = time.time()

        try:
            doc = parse(pdf_path)
            write_document(doc)

            # 提取并写入图片（失败不阻断文档入库）
            img_count = 0
            try:
                img_count = _extract_and_store_images(pdf_path, doc.doc_id, doc.sections)
            except Exception as img_err:
                logger.warning("图片提取步骤失败 %s: %s", doc.doc_id, img_err)

            elapsed = time.time() - start

            if file_key not in completed_set:
                progress["completed"].append(file_key)
                completed_set.add(file_key)

            progress["failed"].pop(file_key, None)
            save_progress(progress)

            img_info = f" {img_count} 张图片" if img_count else ""
            print(f"✓ {doc.doc_id} ({len(doc.sections)} 章节{img_info}) {elapsed:.1f}s")
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