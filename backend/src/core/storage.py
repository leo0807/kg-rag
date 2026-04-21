from __future__ import annotations

"""
src/core/storage.py
MinIO / S3-compatible 对象存储客户端封装

支持环境变量切换本地 MinIO 和云存储（AWS S3 / 阿里云 OSS 等 S3 兼容服务）。
通过 settings.STORAGE_ENDPOINT 区分：
  - http://...  → 本地 MinIO（path-style addressing）
  - 空字符串    → AWS S3（virtual-hosted-style）
"""
import io
import logging
from pathlib import Path
from typing import Generator

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .config import settings

logger = logging.getLogger(__name__)

# ── 存储桶名称常量 ────────────────────────────────────────────────────────────
BUCKET_RAW_DOCUMENTS    = "raw-documents"
BUCKET_SNAPSHOTS        = "snapshots"
BUCKET_EXTRACTED_IMAGES = "extracted-images"
BUCKET_PREVIEWS         = "previews"

ALL_BUCKETS = [BUCKET_RAW_DOCUMENTS, BUCKET_SNAPSHOTS, BUCKET_EXTRACTED_IMAGES, BUCKET_PREVIEWS]


def _make_client():
    """
    创建 boto3 S3 客户端。

    本地 MinIO 需要：
      - endpoint_url 指向 MinIO API 地址
      - path-style addressing（S3ForcePathStyle=True）
    AWS S3 / 云存储则直接使用默认配置。
    """
    is_local = bool(settings.STORAGE_ENDPOINT)
    kwargs = dict(
        service_name         = "s3",
        aws_access_key_id    = settings.STORAGE_ACCESS_KEY,
        aws_secret_access_key= settings.STORAGE_SECRET_KEY,
        region_name          = settings.STORAGE_REGION,
    )
    if is_local:
        kwargs["endpoint_url"] = settings.STORAGE_ENDPOINT
        kwargs["config"]       = Config(signature_version="s3v4", s3={"addressing_style": "path"})

    return boto3.client(**kwargs)


# 模块级单例（延迟初始化）
_client = None


def get_client():
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# ── 存储桶初始化 ──────────────────────────────────────────────────────────────

def ensure_buckets() -> None:
    """
    确保所有必需的存储桶存在；不存在则自动创建。
    在应用启动时调用（startup.py lifespan）。
    """
    client = get_client()
    for bucket in ALL_BUCKETS:
        try:
            client.head_bucket(Bucket=bucket)
            logger.debug("存储桶已存在: %s", bucket)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchBucket"):
                client.create_bucket(Bucket=bucket)
                logger.info("已创建存储桶: %s", bucket)
            else:
                raise


# ── 核心操作 ──────────────────────────────────────────────────────────────────

def upload_file(bucket: str, key: str, file_path: str | Path) -> str:
    """
    上传本地文件到指定存储桶。

    Args:
        bucket: 存储桶名称
        key: 对象键（即存储路径，如 "abc123/report.pdf"）
        file_path: 本地文件路径

    Returns:
        对象的完整 key（可传给 get_url 获取访问链接）
    """
    client = get_client()
    client.upload_file(str(file_path), bucket, key)
    logger.info("上传完成: s3://%s/%s", bucket, key)
    return key


def upload_bytes(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """
    上传字节数据到指定存储桶（无需临时文件）。

    Returns:
        对象的完整 key
    """
    client = get_client()
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    logger.info("上传完成: s3://%s/%s (%d bytes)", bucket, key, len(data))
    return key


def download_file(bucket: str, key: str, dest_path: str | Path) -> None:
    """
    下载对象到本地路径。

    Args:
        bucket: 存储桶名称
        key: 对象键
        dest_path: 本地目标路径
    """
    client = get_client()
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    client.download_file(bucket, key, str(dest_path))
    logger.info("下载完成: s3://%s/%s → %s", bucket, key, dest_path)


def download_bytes(bucket: str, key: str) -> bytes:
    """下载对象并返回字节内容，不写磁盘。"""
    client = get_client()
    buf = io.BytesIO()
    client.download_fileobj(bucket, key, buf)
    return buf.getvalue()


def get_url(
    bucket: str,
    key: str,
    expires: int = 3600,
    inline: bool = False,
    content_type: str | None = None,
) -> str:
    """
    生成预签名访问链接（默认有效期 1 小时）。

    对于本地 MinIO，将 endpoint 替换为 STORAGE_PUBLIC_URL（供浏览器访问）。

    Args:
        bucket:       存储桶名称
        key:          对象键
        expires:      链接有效期（秒）
        inline:       True 时在响应中注入 Content-Disposition: inline，
                      使浏览器在 iframe 内预览而非触发下载
        content_type: 覆盖响应 Content-Type（如 "application/pdf"）

    Returns:
        预签名 URL 字符串
    """
    client = get_client()
    params: dict = {"Bucket": bucket, "Key": key}
    if inline:
        params["ResponseContentDisposition"] = "inline"
    if content_type:
        params["ResponseContentType"] = content_type
    url = client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires,
    )
    # 将内网 endpoint 替换为对外可访问的地址
    if settings.STORAGE_PUBLIC_URL and settings.STORAGE_ENDPOINT:
        url = url.replace(settings.STORAGE_ENDPOINT, settings.STORAGE_PUBLIC_URL, 1)
    return url


def delete_file(bucket: str, key: str) -> None:
    """删除存储桶中的单个对象。"""
    client = get_client()
    client.delete_object(Bucket=bucket, Key=key)
    logger.info("已删除: s3://%s/%s", bucket, key)


def delete_files(bucket: str, keys: list[str]) -> None:
    """批量删除存储桶中的多个对象（最多 1000 个/次）。"""
    if not keys:
        return
    client = get_client()
    client.delete_objects(
        Bucket=bucket,
        Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
    )
    logger.info("批量删除 %d 个对象: s3://%s", len(keys), bucket)


def list_files(bucket: str, prefix: str = "") -> Generator[str, None, None]:
    """
    列出存储桶中指定前缀下的所有对象键（支持分页，无数量上限）。

    Args:
        bucket: 存储桶名称
        prefix: 键前缀过滤（如 "abc123/" 列出某文档下所有文件）

    Yields:
        每个对象的键字符串
    """
    client = get_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def object_exists(bucket: str, key: str) -> bool:
    """检查对象是否存在（head_object，不下载内容）。"""
    client = get_client()
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
