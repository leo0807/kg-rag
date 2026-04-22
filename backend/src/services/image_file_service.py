import tempfile
from pathlib import Path
from typing import Callable, Optional, Tuple


def resolve_image_binary_path(
    image_id: str,
    local_path: Optional[str],
    minio_path: Optional[str],
    download_image_bytes: Optional[Callable[[str], bytes]] = None,
) -> Tuple[Path, Optional[Path]]:
    """返回可供分析读取的本地图片路径，以及需要清理的临时文件。"""
    if local_path:
        candidate = Path(local_path)
        if candidate.exists():
            return candidate, None

    if not minio_path:
        raise FileNotFoundError(f"图片 {image_id} 缺少可用文件路径")

    if download_image_bytes is None:
        from ..core.storage import BUCKET_EXTRACTED_IMAGES, download_bytes

        def _download_from_storage(key: str) -> bytes:
            return download_bytes(BUCKET_EXTRACTED_IMAGES, key)

        download_image_bytes = _download_from_storage

    suffix = Path(minio_path).suffix or ".jpg"
    temp_path = Path(tempfile.gettempdir()) / f"{image_id}{suffix}"
    temp_path.write_bytes(download_image_bytes(minio_path))
    return temp_path, temp_path
