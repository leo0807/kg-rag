import logging
from fastapi import UploadFile, HTTPException
from ...core.config import settings

log = logging.getLogger(__name__)

PDF_ONLY = frozenset({"application/pdf"})
DOCUMENT_TYPES = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
})

MAGIC_BYTES_MAP: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
    "application/msword": (b"\xd0\xcf\x11\xe0",),
}


async def validate_upload(
    file: UploadFile,
    allowed_types: frozenset[str] | None = None,
    max_bytes: int | None = None,
) -> bytes:
    """
    校验上传文件。
    1. MIME 类型白名单
    2. 文件非空且不超大小上限
    3. magic number 匹配（防止扩展名伪装）

    Returns: 文件内容（bytes），调用方直接写盘即可。
    Raises: HTTPException(400) on any validation failure.
    """
    allowed_types = allowed_types or PDF_ONLY
    max_bytes = max_bytes if max_bytes is not None else settings.MAX_UPLOAD_FILE_BYTES

    if file.content_type not in allowed_types:
        log.warning(
            "Rejected upload: filename=%r content_type=%r allowed=%r",
            file.filename, file.content_type, sorted(allowed_types),
        )
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {file.content_type!r}",
        )

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    if len(content) > max_bytes:
        log.warning(
            "Rejected upload: filename=%r size=%d > max=%d",
            file.filename, len(content), max_bytes,
        )
        raise HTTPException(
            status_code=400,
            detail=f"文件过大（{len(content)} bytes），上限 {max_bytes} bytes",
        )

    expected_magics = MAGIC_BYTES_MAP.get(file.content_type, ())
    if expected_magics and not any(content.startswith(magic) for magic in expected_magics):
        log.warning(
            "Rejected upload: filename=%r content_type=%r magic=%r (mismatch)",
            file.filename, file.content_type, content[:8],
        )
        raise HTTPException(
            status_code=400,
            detail="文件 magic number 不匹配，疑似伪装",
        )

    log.info(
        "Upload validated: filename=%r type=%r size=%d",
        file.filename,
        file.content_type,
        len(content),
    )
    return content
