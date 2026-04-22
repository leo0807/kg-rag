from pathlib import Path

import pytest

from src.services.image_file_service import resolve_image_binary_path


def test_resolve_image_binary_path_prefers_existing_local_file(tmp_path):
    local_image = tmp_path / "img.png"
    local_image.write_bytes(b"local")

    path, cleanup = resolve_image_binary_path(
        image_id="img-1",
        local_path=str(local_image),
        minio_path="bucket/key.png",
    )

    assert path == local_image
    assert cleanup is None


def test_resolve_image_binary_path_downloads_from_minio_when_local_missing(tmp_path, monkeypatch):
    temp_root = tmp_path / "tmp"
    temp_root.mkdir()
    monkeypatch.setattr("src.services.image_file_service.tempfile.gettempdir", lambda: str(temp_root))

    path, cleanup = resolve_image_binary_path(
        image_id="img-2",
        local_path="",
        minio_path="CPS1000/1_1.jpeg",
        download_image_bytes=lambda _: b"remote-bytes",
    )

    assert path.exists()
    assert cleanup == path
    assert path.read_bytes() == b"remote-bytes"


def test_resolve_image_binary_path_raises_when_no_source_available():
    with pytest.raises(FileNotFoundError):
        resolve_image_binary_path(
            image_id="img-3",
            local_path="",
            minio_path="",
        )
