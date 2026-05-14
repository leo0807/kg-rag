from __future__ import annotations

import os
import re
import subprocess
import shutil
from pathlib import Path

_OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_OPTION_RE = re.compile(r"^\s*([A-HＡ-Ｈ])[\s、\.．\)）]+(.+?)\s*$")
_OPTION_BLOCK_RE = re.compile(
    r'(?:^|\n)\s*([A-HＡ-Ｈ])\s*[、．.）\)]\s*(.+?)(?=\n\s*[A-HＡ-Ｈ]\s*[、．.）\)]|$)',
    re.MULTILINE | re.DOTALL,
)
_OPTION_INLINE_RE = re.compile(
    r'([A-HＡ-Ｈ])\s*[、．.）\)\s]\s*([^A-HＡ-Ｈ]+?)(?=\s+[A-HＡ-Ｈ]\s*[、．.）\)\s]|$)',
    re.DOTALL,
)
_COMBO_MARKER_RE = re.compile(r'[①②③④⑤⑥⑦⑧]|[\-→]')
_DOC_ID_RE = re.compile(r"(?:doc_id|docid|来源|规范|文档来源)\s*[:：=]\s*(CPS\d+)", re.IGNORECASE)


def _find_soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def normalize_option_label(label: str) -> str:
    label = label.strip().upper()
    return label.translate(str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH"))


def identify_answer_options(options: dict[str, str]) -> dict[str, str]:
    if len(options) <= 4:
        return options
    keys = list(options.keys())
    if len(keys) < 6 or len(keys) % 2 != 0:
        return options
    midpoint = len(keys) // 2
    first_half = keys[:midpoint]
    second_half = keys[midpoint:]
    if not second_half or not all(_COMBO_MARKER_RE.search(options.get(letter, "") or "") for letter in second_half):
        return options
    if any(_COMBO_MARKER_RE.search(options.get(letter, "") or "") for letter in first_half):
        return options
    return {letter: options[letter] for letter in second_half}


def parse_options_from_text(text: str) -> tuple[dict[str, str], str]:
    text = text or ""
    matches = list(_OPTION_BLOCK_RE.finditer(text))
    if len(matches) >= 2:
        options = {normalize_option_label(m.group(1)): m.group(2).strip().rstrip("，。、；;") for m in matches}
        options = identify_answer_options(options)
        return options, text[: matches[0].start()].strip()
    matches = list(_OPTION_INLINE_RE.finditer(text))
    if len(matches) >= 2:
        options = {normalize_option_label(m.group(1)): m.group(2).strip().rstrip("，。、；;") for m in matches}
        options = identify_answer_options(options)
        return options, text[: matches[0].start()].strip()
    return {}, ""


def convert_legacy_word_to_docx(src: Path, out_dir: Path) -> Path:
    def _run_convert(source: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = "/tmp"
        return subprocess.run(
            [
                _find_soffice(),
                "--headless",
                "--norestore",
                "--convert-to",
                "docx:MS Word 2007 XML",
                "--outdir",
                str(out_dir),
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

    def _try_convert(source: Path) -> Path | None:
        result = _run_convert(source)
        converted = out_dir / f"{source.stem}.docx"
        if result.returncode == 0 and converted.exists():
            return converted
        return None

    converted = _try_convert(src)
    if converted:
        return converted
    if src.suffix.lower() == ".wps":
        alias = out_dir / f"{src.stem}.doc"
        alias.write_bytes(src.read_bytes())
        converted = _try_convert(alias)
        if converted:
            return converted
    fallback = sorted(out_dir.glob("*.docx"), key=lambda p: p.stat().st_mtime, reverse=True)
    if fallback:
        return fallback[0]
    raise ValueError("DOC/WPS 转换失败，请确认文件能被 LibreOffice 正常打开")
