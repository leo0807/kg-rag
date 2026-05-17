import logging
from fastapi import UploadFile, HTTPException
from ...core.config import settings

log = logging.getLogger(__name__)

# PDF magic number: %PDF-（25 50 44 46 2D）
_PDF_MAGIC = b"%PDF-"

ALLOWED_MIME_TYPES = {"application/pdf"}


async def validate_upload(
    file: UploadFile,
    max_bytes: int | None = None,
) -> bytes:
    """
    校验上传文件（PDF 专用）：
    1. MIME 类型白名单
    2. 文件非空且不超大小上限
    3. magic number 匹配（防止扩展名伪装）

    Returns: 文件内容（bytes），调用方直接写盘即可。
    Raises: HTTPException(400) on any validation failure.
    """
    max_bytes = max_bytes if max_bytes is not None else settings.MAX_UPLOAD_FILE_BYTES

    if file.content_type not in ALLOWED_MIME_TYPES:
        log.warning(
            "Rejected upload: filename=%r content_type=%r",
            file.filename, file.content_type,
        )
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {file.content_type!r}，仅支持 PDF",
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

    if not content.startswith(_PDF_MAGIC):
        log.warning(
            "Rejected upload: filename=%r magic=%r (not PDF)",
            file.filename, content[:8],
        )
        raise HTTPException(
            status_code=400,
            detail="文件不是有效的 PDF（magic number 不匹配）",
        )

    log.info("Upload validated: filename=%r size=%d", file.filename, len(content))
    return content
