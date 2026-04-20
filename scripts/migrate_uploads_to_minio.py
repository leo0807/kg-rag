#!/usr/bin/env python3
"""
migrate_uploads_to_minio.py
将本地 uploads/ 和 snapshots/ 中尚未迁移的文件批量上传到 MinIO。

第一阶段：uploads/*.pdf / *.docx / *.doc → raw-documents 桶
第二阶段：uploads/images/*              → extracted-images 桶
第三阶段：snapshots/**/*.json           → snapshots 桶

运行前提：
  - docker compose 已启动（MinIO / Neo4j 可访问）
  - 在项目根目录执行：python scripts/migrate_uploads_to_minio.py
  - 或在 backend/ 目录执行（相对路径 uploads/、snapshots/ 均可）
"""
import json
import logging
import os
import sys
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from neo4j import GraphDatabase

# ── 配置 ──────────────────────────────────────────────────────────────────────
MINIO_ENDPOINT   = os.getenv("STORAGE_ENDPOINT",   "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("STORAGE_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("STORAGE_SECRET_KEY", "minioadmin")
MINIO_REGION     = os.getenv("STORAGE_REGION",     "us-east-1")

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aviation123")

BUCKET_RAW       = "raw-documents"
BUCKET_IMAGES    = "extracted-images"
BUCKET_SNAPSHOTS = "snapshots"

DOC_EXTS = {".pdf", ".docx", ".doc"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── 客户端初始化 ──────────────────────────────────────────────────────────────

def make_s3():
    return boto3.client(
        "s3",
        endpoint_url         = MINIO_ENDPOINT,
        aws_access_key_id    = MINIO_ACCESS_KEY,
        aws_secret_access_key= MINIO_SECRET_KEY,
        region_name          = MINIO_REGION,
        config               = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def upload_file(s3, bucket: str, key: str, path: Path) -> None:
    s3.upload_file(str(path), bucket, key)


def upload_bytes(s3, bucket: str, key: str, data: bytes, ct: str = "application/octet-stream") -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=ct)


# ── 查找脚本运行目录 ───────────────────────────────────────────────────────────

def find_root() -> Path:
    """从当前目录或 backend/ 向上找 uploads/ 目录。"""
    for candidate in (Path.cwd(), Path.cwd() / "backend", Path(__file__).parent.parent / "backend"):
        if (candidate / "uploads").exists():
            return candidate
    log.error("找不到 uploads/ 目录，请在项目根目录或 backend/ 下运行此脚本")
    sys.exit(1)


# ── 阶段一：PDF / DOCX → raw-documents ───────────────────────────────────────

def migrate_documents(s3, driver, uploads_dir: Path) -> tuple[int, int, list[str]]:
    """返回 (成功数, 跳过数, 失败文件列表)"""
    ok = skipped = 0
    failures: list[str] = []

    # 只扫描 uploads/ 根目录，排除 images/ 和 _converted/ 子目录
    candidates = [
        f for f in uploads_dir.iterdir()
        if f.is_file() and f.suffix.lower() in DOC_EXTS
    ]
    total = len(candidates)
    log.info("=== 阶段一：文档迁移  共 %d 个文件 ===", total)

    for idx, local_path in enumerate(sorted(candidates), 1):
        filename = local_path.name
        # 从文件名提取 doc_id：格式为 {hash}_{DOC_ID}_{title}.pdf
        # doc_id 是第二段（按 _ 分割，首段是 12 位 hash）
        parts = filename.replace(local_path.suffix, "").split("_")
        doc_id = parts[1] if len(parts) >= 2 else parts[0]
        minio_key = f"{doc_id}{local_path.suffix.lower()}"

        print(f"\r  [{idx:4d}/{total}] {filename[:60]:<60}", end="", flush=True)

        try:
            # 检查 MinIO 是否已存在
            if object_exists(s3, BUCKET_RAW, minio_key):
                log.debug("已存在，跳过: %s", minio_key)
                skipped += 1
                # 确保 Neo4j 有 storage_key（防止数据不一致）
                _set_storage_key(driver, doc_id, minio_key)
                local_path.unlink(missing_ok=True)
                continue

            # 上传
            upload_file(s3, BUCKET_RAW, minio_key, local_path)

            # 更新 Neo4j storage_key
            _set_storage_key(driver, doc_id, minio_key)

            # 删除本地文件
            local_path.unlink(missing_ok=True)
            ok += 1

        except Exception as e:
            log.warning("\n  失败 %s: %s", filename, e)
            failures.append(f"{filename}: {e}")

    print()  # 换行
    return ok, skipped, failures


def _set_storage_key(driver, doc_id: str, key: str) -> None:
    with driver.session() as s:
        s.run(
            "MATCH (d:Document {name: $doc_id}) SET d.storage_key = $key",
            doc_id=doc_id, key=key,
        )


# ── 阶段二：uploads/images/* → extracted-images ───────────────────────────────

def migrate_images(s3, driver, uploads_dir: Path) -> tuple[int, int, list[str]]:
    images_dir = uploads_dir / "images"
    if not images_dir.exists():
        log.info("uploads/images/ 不存在，跳过")
        return 0, 0, []

    candidates = [f for f in images_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
    total = len(candidates)
    log.info("=== 阶段二：图片迁移  共 %d 个文件 ===", total)

    ok = skipped = 0
    failures: list[str] = []

    for idx, local_path in enumerate(sorted(candidates), 1):
        filename = local_path.name  # e.g. CPS6010_page1_img0.jpeg
        # 解析 doc_id：取 _page 之前的部分
        doc_id = filename.split("_page")[0] if "_page" in filename else filename.split("_")[0]
        ext = local_path.suffix.lower().lstrip(".")
        minio_key = f"{doc_id}/{filename}"

        print(f"\r  [{idx:5d}/{total}] {filename[:60]:<60}", end="", flush=True)

        try:
            if object_exists(s3, BUCKET_IMAGES, minio_key):
                skipped += 1
                _set_image_minio_path(driver, filename, minio_key)
                local_path.unlink(missing_ok=True)
                continue

            img_bytes = local_path.read_bytes()
            ct = f"image/{ext}" if ext in ("jpeg", "jpg", "png", "gif", "webp") else "application/octet-stream"
            upload_bytes(s3, BUCKET_IMAGES, minio_key, img_bytes, ct)

            _set_image_minio_path(driver, filename, minio_key)
            local_path.unlink(missing_ok=True)
            ok += 1

        except Exception as e:
            log.warning("\n  失败 %s: %s", filename, e)
            failures.append(f"{filename}: {e}")

    print()
    return ok, skipped, failures


def _set_image_minio_path(driver, filename: str, minio_key: str) -> None:
    # image_id 是去掉扩展名的文件名
    image_id = Path(filename).stem
    with driver.session() as s:
        s.run(
            "MATCH (i:Image {image_id: $iid}) SET i.minio_path = $key",
            iid=image_id, key=minio_key,
        )


# ── 阶段三：snapshots/**/*.json → MinIO snapshots 桶 ─────────────────────────

def migrate_snapshots(s3, snapshots_dir: Path) -> tuple[int, int, list[str]]:
    if not snapshots_dir.exists():
        log.info("snapshots/ 目录不存在，跳过")
        return 0, 0, []

    candidates = list(snapshots_dir.rglob("snap_*.json"))
    total = len(candidates)
    log.info("=== 阶段三：快照迁移  共 %d 个文件 ===", total)

    ok = skipped = 0
    failures: list[str] = []

    for idx, local_path in enumerate(sorted(candidates), 1):
        # 路径结构: snapshots/{doc_id}/snap_{ts}.json
        doc_id      = local_path.parent.name
        snapshot_id = local_path.stem
        minio_key   = f"{doc_id}/{snapshot_id}.json"

        print(f"\r  [{idx:3d}/{total}] {minio_key:<50}", end="", flush=True)

        try:
            if object_exists(s3, BUCKET_SNAPSHOTS, minio_key):
                skipped += 1
                continue

            data = local_path.read_bytes()
            upload_bytes(s3, BUCKET_SNAPSHOTS, minio_key, data, "application/json")
            ok += 1

        except Exception as e:
            log.warning("\n  失败 %s: %s", minio_key, e)
            failures.append(f"{minio_key}: {e}")

    print()
    return ok, skipped, failures


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    root = find_root()
    uploads_dir   = root / "uploads"
    snapshots_dir = root / "snapshots"

    log.info("工作目录: %s", root)
    log.info("MinIO:   %s", MINIO_ENDPOINT)
    log.info("Neo4j:   %s", NEO4J_URI)

    s3 = make_s3()
    # 确认桶存在
    for bucket in (BUCKET_RAW, BUCKET_IMAGES, BUCKET_SNAPSHOTS):
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                s3.create_bucket(Bucket=bucket)
                log.info("已创建存储桶: %s", bucket)
            else:
                raise

    neo4j = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        # 阶段一
        d_ok, d_skip, d_fail = migrate_documents(s3, neo4j, uploads_dir)

        # 阶段二
        i_ok, i_skip, i_fail = migrate_images(s3, neo4j, uploads_dir)

        # 阶段三
        s_ok, s_skip, s_fail = migrate_snapshots(s3, snapshots_dir)

    finally:
        neo4j.close()

    # ── 汇总报告 ──────────────────────────────────────────────────────────────
    all_failures = d_fail + i_fail + s_fail
    print("\n" + "=" * 60)
    print("迁移完成报告")
    print("=" * 60)
    print(f"  文档 (raw-documents):    成功 {d_ok:4d}  跳过 {d_skip:4d}  失败 {len(d_fail):3d}")
    print(f"  图片 (extracted-images): 成功 {i_ok:5d}  跳过 {i_skip:5d}  失败 {len(i_fail):3d}")
    print(f"  快照 (snapshots):        成功 {s_ok:3d}  跳过 {s_skip:3d}  失败 {len(s_fail):3d}")
    print(f"  合计成功: {d_ok + i_ok + s_ok}")
    print(f"  合计失败: {len(all_failures)}")

    if all_failures:
        print("\n失败文件列表:")
        for f in all_failures:
            print(f"  - {f}")

    # 统计剩余文件数
    remaining_docs   = sum(1 for f in uploads_dir.iterdir()
                           if f.is_file() and f.suffix.lower() in DOC_EXTS) if uploads_dir.exists() else 0
    remaining_images = sum(1 for f in (uploads_dir / "images").iterdir()
                           if f.is_file()) if (uploads_dir / "images").exists() else 0
    print(f"\nuploads/ 剩余文档: {remaining_docs}")
    print(f"uploads/images/ 剩余图片: {remaining_images}")
    print("=" * 60)


if __name__ == "__main__":
    main()
