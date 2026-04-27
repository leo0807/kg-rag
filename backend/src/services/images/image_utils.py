from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

IMAGE_DIR = Path("uploads/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ExtractedImage:
    image_id:     str        # 唯一ID
    doc_id:       str
    page:         int
    path:         str        # 本地文件路径（处理期间保留）
    width:        int
    height:       int
    content_hash: str
    caption:      str = ""
    minio_key:    str = ""
    chunk_id:     str = ""


def compute_image_content_hash(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def register_image_hash(seen_hashes: set[str], image_bytes: bytes) -> tuple[str, bool]:
    content_hash = compute_image_content_hash(image_bytes)
    if content_hash in seen_hashes:
        return content_hash, True
    seen_hashes.add(content_hash)
    return content_hash, False


def _upload_to_minio(image_data: bytes, image_id: str, ext: str) -> str:
    try:
        from ...core.storage import upload_bytes, BUCKET_EXTRACTED_IMAGES
        key = f"{image_id}.{ext}"
        upload_bytes(BUCKET_EXTRACTED_IMAGES, key, image_data, content_type=f"image/{ext}")
        return key
    except Exception as e:
        logger.warning("图片上传 MinIO 失败 image_id=%s: %s", image_id, e)
        return ""


def persist_image_bytes(*, image_id: str, ext: str, image_bytes: bytes) -> tuple[str, str]:
    """保存到本地并尽量上传 MinIO。返回 (local_path, minio_key)。"""
    img_path = IMAGE_DIR / f"{image_id}.{ext}"
    with open(img_path, "wb") as f:
        f.write(image_bytes)
    minio_key = _upload_to_minio(image_bytes, image_id, ext)
    if minio_key:
        try:
            img_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("删除本地临时图片失败 %s: %s", img_path, exc)
    return (str(img_path) if not minio_key else "", minio_key)
