from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _extract_doc_id_from_filename(path: Path) -> str:
    m = re.search(r'(CPS\d+)', path.name, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _find_soffice() -> str | None:
    import os as _os
    import shutil as _shutil
    import subprocess as _subprocess
    import glob as _glob

    def _works(path: str) -> bool:
        if not (_os.path.isfile(path) and _os.access(path, _os.X_OK)):
            return False
        try:
            r = _subprocess.run(
                [path, "--version"],
                stdout=_subprocess.PIPE,
                stderr=_subprocess.PIPE,
                timeout=8,
            )
            return r.returncode == 0
        except Exception:
            return False

    candidates = [
        "/usr/bin/soffice",
        "/usr/lib/libreoffice/program/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/Applications/LibreOffice 7.app/Contents/MacOS/soffice",
        "/Applications/LibreOffice 24.app/Contents/MacOS/soffice",
        _os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        *_glob.glob("/usr/local/Caskroom/libreoffice/*/LibreOffice.app/Contents/MacOS/soffice"),
        *_glob.glob("/opt/homebrew/Caskroom/libreoffice/*/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    for p in candidates:
        if _works(p):
            return p

    for name in ("soffice", "libreoffice"):
        found = _shutil.which(name)
        if found and _works(found):
            return found

    return None


def _detect_doc_format(path: Path) -> str:
    try:
        import zipfile as _zf
        with _zf.ZipFile(path) as z:
            names = z.namelist()
            if any(n.startswith("visio/") for n in names):
                return "visio"
            if "word/document.xml" in names:
                return "docx"
    except Exception:
        pass
    return "doc_binary"


def _validate_converted_docx(converted: Path) -> None:
    import zipfile as _zf
    try:
        with _zf.ZipFile(converted) as z:
            names = z.namelist()
            if "word/document.xml" not in names:
                raise ValueError(
                    f"转换后文件不含 word/document.xml（实际内容: {names[:6]}），"
                    "原文件可能是 Visio 绘图或其他非 Word 格式。"
                )
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            import re as _re
            text_content = _re.sub(r"<[^>]+>", "", xml)
            if len(text_content.strip()) < 50:
                raise ValueError("转换后文档内容为空，原文件可能是纯绘图文件，无法提取文本。")
    except _zf.BadZipFile:
        raise ValueError("转换后文件不是有效的 ZIP/DOCX 格式。")


def _convert_office_to_pdf(office_path: Path) -> Path:
    import os as _os
    import subprocess as _subprocess

    fmt = _detect_doc_format(office_path)
    if fmt == "visio":
        raise ValueError(
            f"文件 {office_path.name} 是 Visio 绘图文件，无法解析为文档章节。"
        )

    soffice = _find_soffice()
    if not soffice:
        raise RuntimeError(
            "未找到 LibreOffice — 请安装后重启服务，或将文件转换为 PDF 后上传。"
        )

    output_dir = Path("/tmp")
    pdf_path = output_dir / (office_path.stem + ".pdf")

    env = _os.environ.copy()
    env["HOME"] = "/tmp"

    result = _subprocess.run(
        [soffice, "--headless", "--norestore",
         "--convert-to", "pdf",
         "--outdir", str(output_dir),
         str(office_path)],
        capture_output=True, text=True, timeout=180, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转 PDF 失败 (exit {result.returncode}): {result.stderr}")
    if not pdf_path.exists():
        raise RuntimeError(f"转换后 PDF 不存在: {pdf_path}")

    logger.info("LibreOffice 转换完成: %s -> %s (%.1f MB)",
                office_path.name, pdf_path.name, pdf_path.stat().st_size / 1024 / 1024)
    return pdf_path


def _convert_doc_to_docx(path: Path) -> Path:
    import os as _os
    import subprocess as _subprocess

    fmt = _detect_doc_format(path)
    if fmt == "docx":
        return path
    if fmt == "visio":
        raise ValueError(
            f"文件 {path.name} 是 Microsoft Visio 绘图文件，不是 Word 文档，无法解析章节内容。"
            "如需处理，请将 Visio 文件转换为 PDF 后单独上传。"
        )

    soffice = _find_soffice()
    if not soffice:
        raise ValueError(
            "DOC 转换失败：服务器未安装 LibreOffice。"
            "请将文件另存为 .docx 格式后重新上传，或联系管理员安装 LibreOffice。"
        )

    out_dir = path.parent / "_converted"
    out_dir.mkdir(exist_ok=True)
    converted = out_dir / f"{path.stem}.docx"

    env = _os.environ.copy()
    env["HOME"] = "/tmp"

    cmd = [
        soffice, "--headless", "--norestore",
        "--convert-to", "docx:MS Word 2007 XML",
        "--outdir", str(out_dir), str(path),
    ]
    result = _subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转换失败 (exit {result.returncode}): {result.stderr}")
    if not converted.exists():
        raise RuntimeError(f"LibreOffice 转换后文件不存在: {converted}")

    _validate_converted_docx(converted)
    return converted
