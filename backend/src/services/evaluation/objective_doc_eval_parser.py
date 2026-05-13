from __future__ import annotations

import re
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from xml.etree import ElementTree as ET
import logging

from .objective_doc_eval_parse_utils import (
    _DOC_ID_RE,
    _OPTION_LETTERS,
    _OPTION_RE,
    convert_legacy_word_to_docx,
    normalize_option_label,
    parse_options_from_text,
)

_WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
logger = logging.getLogger(__name__)

_QUESTION_START_RE = re.compile(r"^\s*(\d+)[\.、．]\s*(.+?)\s*$")
_QUESTION_SUFFIX_RE = re.compile(r"^\s*(.+?[？?：:])\s*(?:[（(][A-HＡ-Ｈ对错√×][）)])?\s*$")
_ANSWER_KEY_RE = re.compile(r"\s*[（(]([A-HＡ-Ｈ]{1,8}|对|错|√|×)[）)]\s*$")
_RETRIEVAL_BOILERPLATE = {
    "对于", "以下", "下列", "关于", "哪一项", "哪种", "哪个", "何种",
    "正确", "不正确", "错误", "描述", "说法", "方法", "方式", "表述",
    "的是", "是否", "可以", "不能", "能够", "应", "应当", "直接", "进行",
    "选择", "判断", "采用", "使用", "规定", "要求", "问题", "选项", "答案",
}


def _convert_legacy_word_to_docx(src: Path, out_dir: Path) -> Path:
    return convert_legacy_word_to_docx(src, out_dir)


def _extract_docx_paragraphs(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for p in root.iterfind(".//w:p", _WORD_NS):
        text = "".join(node.text or "" for node in p.iterfind(".//w:t", _WORD_NS)).strip()
        if text:
            paragraphs.append(re.sub(r"\s+", " ", text))
    return paragraphs


def _load_word_lines(filename: str, data: bytes) -> list[str]:
    lower = filename.lower()
    if not lower.endswith((".docx", ".doc", ".wps")):
        raise ValueError("仅支持 .docx / .doc / .wps 客观题文档")
    with TemporaryDirectory(prefix="objective_eval_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        src = tmpdir_path / filename
        src.write_bytes(data)
        docx = src if lower.endswith(".docx") else _convert_legacy_word_to_docx(src, tmpdir_path)
        return _extract_docx_paragraphs(docx)


def _is_section_heading(line: str) -> bool:
    text = line.strip().replace(" ", "")
    return bool(re.match(r"^[一二三四五六七八九十]+、", text)) or text in {"试题库", "单项选择", "多项选择", "判断题"}


def _is_option_line(line: str) -> bool:
    return bool(_OPTION_RE.match(line))


def _is_question_start(line: str) -> bool:
    if _is_option_line(line):
        return False
    if _QUESTION_START_RE.match(line):
        return True
    if _ANSWER_KEY_RE.search(line):
        return True
    if _QUESTION_SUFFIX_RE.match(line):
        return True
    return False


def _strip_answer_key(text: str) -> str:
    return _ANSWER_KEY_RE.sub("", text).strip()


def _extract_answer_key(text: str) -> tuple[str, str]:
    m = _ANSWER_KEY_RE.search(text or "")
    if not m:
        return (text or "").strip(), ""
    key = normalize_option_label(m.group(1))
    if key in {"√", "×"}:
        key = "对" if key == "√" else "错"
    return _ANSWER_KEY_RE.sub("", text or "").strip(), key


def _answer_mode_from_key(answer_key: str) -> str:
    if not answer_key:
        return "freeform"
    if answer_key in {"对", "错"}:
        return "judge"
    if len(answer_key) > 1:
        return "multi_choice"
    return "single_choice"


def _choice_labels(option_labels: list[str]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for label in option_labels:
        normalized = normalize_option_label(label)
        if normalized in _OPTION_LETTERS and normalized not in seen:
            labels.append(normalized)
            seen.add(normalized)
    return labels


def _extract_multi_choice_labels(text: str, option_labels: list[str]) -> list[str]:
    _CHOICE_LABEL_RE = re.compile(r"(?<![A-Z0-9Ａ-Ｈ])([A-HＡ-Ｈ]{1,8})(?![A-Z0-9Ａ-Ｈ])")
    _SINGLE_CHOICE_LABEL_RE = re.compile(r"(?<![A-Z0-9Ａ-Ｈ])([A-HＡ-Ｈ])(?![A-Z0-9Ａ-Ｈ])")
    allowed = set(_choice_labels(option_labels)) or set(_OPTION_LETTERS[:8])
    normalized = normalize_option_label(text or "")
    matches: list[str] = []
    compact = _CHOICE_LABEL_RE.search(normalized)
    if compact:
        candidate = compact.group(1)
        if len(candidate) > 1:
            for ch in candidate:
                if ch in allowed and ch not in matches:
                    matches.append(ch)
            if len(matches) > 1:
                return matches
    for ch in _SINGLE_CHOICE_LABEL_RE.findall(normalized):
        if ch in allowed and ch not in matches:
            matches.append(ch)
    return matches


def _clean_reason_text(text: str) -> str:
    cleaned = (text or "").strip().strip("`")
    cleaned = re.sub(
        r"^\s*final_answer\s*[:：=]\s*(?:\\?['\"])?[A-HＡ-Ｈ对错√×]{1,8}(?:\\?['\"])?\s*,?\s*",
        "", cleaned, flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^\s*reason\s*[:：=]\s*['\"]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*[,，；;]+\s*", "", cleaned)
    cleaned = re.sub(r'^[\s{[(<"\']+', "", cleaned)
    cleaned = re.sub(r'[\s}\])>"\']+$', "", cleaned)
    return cleaned.strip()


def _build_objective_retrieval_query(question: str, options: list[dict[str, str]]) -> str:
    text = question
    if options:
        text = f"{question}\n" + "\n".join(opt.get("text", "") for opt in options if opt.get("text"))
    for phrase in sorted(_RETRIEVAL_BOILERPLATE, key=len, reverse=True):
        text = text.replace(phrase, " ")
    for ch in "（）()【】[]？?：:。，、；":
        text = text.replace(ch, " ")
    text = re.sub(r"\d+\s*[\.、．]?\s*", " ", text)
    text = re.sub(r"[A-HＡ-Ｈ]\s*[\.、．\)]\s*", " ", text)
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\-]{2,}", text)
    keywords: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in _RETRIEVAL_BOILERPLATE or token.startswith(("第", "选项", "答案")):
            continue
        if token not in seen:
            keywords.append(token)
            seen.add(token)
    keywords = sorted(keywords, key=lambda t: (len(t) < 4, len(t)))
    return " ".join(keywords[:12]) if keywords else question


def _split_question_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        text = line.strip()
        if not text or _is_section_heading(text):
            continue
        if _is_question_start(text):
            if current:
                blocks.append(current)
            current = [text]
            continue
        if current:
            current.append(text)
    if current:
        blocks.append(current)
    return blocks


def _parse_question_block(block: list[str], seq: int) -> dict[str, Any] | None:
    if not block:
        return None
    first = block[0]
    doc_id = ""
    for line in block:
        m = _DOC_ID_RE.search(line)
        if m:
            doc_id = m.group(1).strip()
            break
    match = _QUESTION_START_RE.match(first)
    if match:
        display_no = match.group(1)
        stem, answer_key = _extract_answer_key(match.group(2))
    else:
        display_no = str(seq)
        stem, answer_key = _extract_answer_key(first)

    rest = block[1:]
    options: list[dict[str, str]] = []
    stem_extra: list[str] = []
    saw_labeled_option = False
    parsed_options, prefix_text = parse_options_from_text("\n".join(rest))
    if len(parsed_options) >= 2:
        options = [{"label": k, "text": v} for k, v in parsed_options.items()]
        if prefix_text:
            stem = f"{stem} {prefix_text}".strip()
        question_type = "choice"
        if answer_key:
            question_type = "multi_choice" if len(answer_key) > 1 else "choice"
        if not answer_key and (re.search(r"(对还是错|对吗|错吗|判断|是否正确|是否错误)", stem) or not options):
            question_type = "judge" if not options else question_type
        return {"display_no": display_no, "question": stem, "options": options, "question_type": question_type, "answer_key": answer_key, "doc_id": doc_id}
    for line in rest:
        option_match = _OPTION_RE.match(line)
        if option_match:
            saw_labeled_option = True
            options.append({"label": normalize_option_label(option_match.group(1)), "text": option_match.group(2).strip()})
            continue
        if saw_labeled_option and options:
            options[-1]["text"] = f"{options[-1]['text']} {line}".strip()
        else:
            stem_extra.append(_strip_answer_key(line))

    if not options and stem_extra:
        unlabeled = [item for item in stem_extra if item]
        if 2 <= len(unlabeled) <= 8:
            options = [{"label": chr(ord("A") + idx), "text": text} for idx, text in enumerate(unlabeled)]
            stem_extra = []
    if stem_extra:
        stem = f"{stem} {' '.join(stem_extra)}".strip()

    question_type = "choice" if options else "unknown"
    if options and answer_key:
        question_type = "multi_choice" if len(answer_key) > 1 else "choice"
    if not options and (answer_key in {"对", "错"} or re.search(r"(对还是错|对吗|错吗|判断|是否正确|是否错误)", stem)):
        question_type = "judge"
    return {"display_no": display_no, "question": stem, "options": options, "question_type": question_type, "answer_key": answer_key, "doc_id": doc_id}


def extract_objective_questions(filename: str, data: bytes) -> list[dict[str, Any]]:
    lines = _load_word_lines(filename, data)
    blocks = _split_question_blocks(lines)
    questions: list[dict[str, Any]] = []
    for idx, block in enumerate(blocks, start=1):
        try:
            item = _parse_question_block(block, idx)
        except Exception as exc:
            logger.warning("客观题块解析失败，已跳过: block=%s, error=%s", block[:3], exc)
            continue
        if item and item["question"]:
            questions.append(item)
    if not questions:
        raise ValueError("未从文档中识别出客观题，请检查题号或选项格式")
    return questions


def _parse_objective_llm_response(raw: str, question_type: str, option_labels: list[str]) -> tuple[str, str]:
    """兼容旧测试/旧调用名。"""
    from .objective_doc_eval_runner import _parse_llm_response

    return _parse_llm_response(raw, question_type, option_labels)
