from __future__ import annotations

import asyncio
import base64
import logging
import re
import tempfile
from pathlib import Path

from .image_analyzer import analyze_image

logger = logging.getLogger(__name__)

_DATA_URI_RE = re.compile(r"^data:(?P<media_type>[^;]+);base64,(?P<data>.+)$", re.DOTALL)
_MAX_IMAGES = 3


def _suffix_for_media_type(media_type: str) -> str:
    subtype = (media_type.split("/", 1)[1] if "/" in media_type else "png").lower()
    if subtype == "jpeg":
        return ".jpg"
    if subtype in {"png", "webp", "gif", "jpg"}:
        return f".{subtype}"
    return ".png"


def _write_data_uri_to_tempfile(data_uri: str) -> Path:
    match = _DATA_URI_RE.match(data_uri.strip())
    if not match:
        raise ValueError("invalid data uri")
    media_type = match.group("media_type")
    raw = base64.b64decode(match.group("data"))
    suffix = _suffix_for_media_type(media_type)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(raw)
        tmp.flush()
    finally:
        tmp.close()
    return Path(tmp.name)


def _format_image_summary(idx: int, analysis: dict) -> str:
    parts: list[str] = [
        f"图片 {idx}：",
        f"- 描述：{analysis.get('description') or '工艺图片'}",
    ]
    tools = analysis.get("tools") or []
    steps = analysis.get("steps") or []
    dimensions = analysis.get("dimensions") or []
    keywords = analysis.get("keywords") or []
    if tools:
        parts.append(f"- 工具：{'、'.join(str(x) for x in tools[:5])}")
    if steps:
        parts.append(f"- 步骤：{'；'.join(str(x) for x in steps[:5])}")
    if dimensions:
        parts.append(f"- 尺寸：{'、'.join(str(x) for x in dimensions[:5])}")
    if keywords:
        parts.append(f"- 关键词：{'、'.join(str(x) for x in keywords[:5])}")
    return "\n".join(parts)


async def build_query_image_context(
    images: list[str],
    caption: str = "",
    max_images: int = _MAX_IMAGES,
) -> str:
    if not images:
        return ""

    summaries: list[str] = []
    limit = min(len(images), max_images)
    for idx, data_uri in enumerate(images[:limit], start=1):
        tmp_path: Path | None = None
        try:
            tmp_path = _write_data_uri_to_tempfile(data_uri)
            analysis = await asyncio.to_thread(
                analyze_image,
                str(tmp_path),
                caption=caption,
            )
            summaries.append(_format_image_summary(idx, analysis))
        except Exception as exc:
            logger.warning("构建查询图片上下文失败 #%s: %s", idx, exc)
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    if not summaries:
        return ""

    if len(images) > limit:
        summaries.append(f"另有 {len(images) - limit} 张图片未展开。")

    return "## 图片补充信息\n\n" + "\n\n".join(summaries)
