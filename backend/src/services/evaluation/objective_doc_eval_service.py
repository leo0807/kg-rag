from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import re
import subprocess
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from xml.etree import ElementTree as ET

from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ...db.models import ObjectiveDocEvalTask
from ..llm_service import get_llm_service

logger = logging.getLogger(__name__)

_tasks: dict[str, dict[str, Any]] = {}
DO_RETRIEVAL: Any | None = None

_WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

_QUESTION_START_RE = re.compile(r"^\s*(\d+)[\.、．]\s*(.+?)\s*$")
_QUESTION_SUFFIX_RE = re.compile(r"^\s*(.+?[？?：:])\s*(?:[（(][A-HＡ-Ｈ对错√×][）)])?\s*$")
_ANSWER_KEY_RE = re.compile(r"\s*[（(]([A-HＡ-Ｈ]{1,8}|对|错|√|×)[）)]\s*$")
_OPTION_RE = re.compile(r"^\s*([A-HＡ-Ｈ])[\s、\.．\)）]+(.+?)\s*$")
_RETRIEVAL_BOILERPLATE = {
    "对于", "以下", "下列", "关于", "哪一项", "哪种", "哪个", "何种",
    "正确", "不正确", "错误", "描述", "说法", "方法", "方式", "表述",
    "的是", "是否", "可以", "不能", "能够", "应", "应当", "直接", "进行",
    "选择", "判断", "采用", "使用", "规定", "要求", "问题", "选项", "答案",
}
_CHOICE_LABEL_RE = re.compile(r"(?<![A-Z0-9Ａ-Ｈ])([A-HＡ-Ｈ]{1,8})(?![A-Z0-9Ａ-Ｈ])")
_SINGLE_CHOICE_LABEL_RE = re.compile(r"(?<![A-Z0-9Ａ-Ｈ])([A-HＡ-Ｈ])(?![A-Z0-9Ａ-Ｈ])")
_ANSWER_HINT_RE = re.compile(
    r"(?:最终答案|正确答案|参考答案|答案|选项|答案为|应为|应选|因此选|所以选)\s*[:：=]?\s*([A-HＡ-Ｈ]{1,8}|对|错|√|×)",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _find_soffice() -> str | None:
    try:
        from ..parsing.parser import _find_soffice as _find_parser_soffice
    except Exception:
        return None
    return _find_parser_soffice()


def _get_do_retrieval():
    global DO_RETRIEVAL
    if callable(DO_RETRIEVAL):
        return DO_RETRIEVAL

    from ...routers.query.core import do_retrieval

    DO_RETRIEVAL = do_retrieval
    return do_retrieval


def _task_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id", ""),
        "filename": task.get("filename", ""),
        "strategy": task.get("strategy", "parallel"),
        "top_k": int(task.get("top_k", 5) or 5),
        "status": task.get("status", "queued"),
        "total": int(task.get("total", 0) or 0),
        "completed": int(task.get("completed", 0) or 0),
        "current_question": task.get("current_question", ""),
        "error": task.get("error", ""),
        "summary": task.get("summary"),
        "results": task.get("results"),
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
    }


async def _persist_task(task: dict[str, Any]) -> None:
    from ...db.session import AsyncSessionLocal, init_tables

    payload = _task_snapshot(task)

    async def _write_once() -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ObjectiveDocEvalTask).where(ObjectiveDocEvalTask.task_id == payload["task_id"])
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = ObjectiveDocEvalTask(**payload)
                db.add(row)
            else:
                for key, value in payload.items():
                    setattr(row, key, value)
            await db.commit()

    try:
        await _write_once()
    except SQLAlchemyError as exc:
        logger.warning("客观题评测结果落库失败，尝试自动初始化表后重试: %s", exc)
        try:
            await init_tables()
            await _write_once()
        except Exception as retry_exc:
            logger.exception("客观题评测结果落库仍然失败: %s", retry_exc)
    except Exception as exc:
        logger.exception("客观题评测结果落库异常: %s", exc)


def _task_from_row(row: ObjectiveDocEvalTask) -> dict[str, Any]:
    return {
        "task_id": row.task_id,
        "filename": row.filename,
        "status": row.status,
        "strategy": row.strategy,
        "top_k": row.top_k,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "total": row.total,
        "completed": row.completed,
        "current_question": row.current_question or "",
        "error": row.error or "",
        "summary": row.summary,
        "results_preview": (row.results or [])[:50],
        "results": row.results or [],
    }


async def _load_task_from_db(task_id: str) -> dict[str, Any]:
    from ...db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ObjectiveDocEvalTask).where(ObjectiveDocEvalTask.task_id == task_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise KeyError(task_id)
        return _task_from_row(row)


def _convert_legacy_word_to_docx(src: Path, out_dir: Path) -> Path:
    soffice = _find_soffice()
    if not soffice:
        raise ValueError("服务器未安装 LibreOffice，无法解析 DOC/WPS 客观题文档")

    env = os.environ.copy()
    env["HOME"] = "/tmp"
    result = subprocess.run(
        [
            soffice,
            "--headless",
            "--norestore",
            "--convert-to",
            "docx:MS Word 2007 XML",
            "--outdir",
            str(out_dir),
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    converted = out_dir / f"{src.stem}.docx"
    if result.returncode != 0 or not converted.exists():
        raise ValueError("DOC/WPS 转换失败，请确认文件能被 LibreOffice 正常打开")
    return converted


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

        if lower.endswith(".docx"):
            docx = src
        else:
            docx = _convert_legacy_word_to_docx(src, tmpdir_path)

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


def _normalize_option_label(label: str) -> str:
    label = label.strip().upper()
    trans = str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH")
    return label.translate(trans)


def _extract_answer_key(text: str) -> tuple[str, str]:
    """从题干末尾提取括号中的答案键，并返回 (清理后的文本, 答案键)。"""
    m = _ANSWER_KEY_RE.search(text or "")
    if not m:
        return (text or "").strip(), ""

    key = _normalize_option_label(m.group(1))
    if key in {"√", "×"}:
        key = "对" if key == "√" else "错"
    cleaned = _ANSWER_KEY_RE.sub("", text or "").strip()
    return cleaned, key


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
        normalized = _normalize_option_label(label)
        if normalized in _OPTION_LETTERS and normalized not in seen:
            labels.append(normalized)
            seen.add(normalized)
    return labels


def _extract_multi_choice_labels(text: str, option_labels: list[str]) -> list[str]:
    allowed = set(_choice_labels(option_labels))
    if not allowed:
        allowed = set(_OPTION_LETTERS[:8])

    normalized = _normalize_option_label(text or "")
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
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^\s*reason\s*[:：=]\s*['\"]?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^\s*[,，；;]+\s*", "", cleaned)
    cleaned = re.sub(r'^[\s{[(<"\']+', "", cleaned)
    cleaned = re.sub(r'[\s}\])>"\']+$', "", cleaned)
    return cleaned.strip()


def _build_objective_retrieval_query(question: str, options: list[dict[str, str]]) -> str:
    """
    生成更适合召回的检索词。
    目标是保留领域关键词，去掉题干里的考试模板词和选项噪声。
    """
    text = question
    if options:
        text = f"{question}\n" + "\n".join(opt.get("text", "") for opt in options if opt.get("text"))

    for phrase in sorted(_RETRIEVAL_BOILERPLATE, key=len, reverse=True):
        text = text.replace(phrase, " ")

    text = text.replace("（", " ").replace("）", " ").replace("(", " ").replace(")", " ")
    text = text.replace("【", " ").replace("】", " ").replace("[", " ").replace("]", " ")
    text = text.replace("？", " ").replace("?", " ").replace("：", " ").replace(":", " ")
    text = text.replace("。", " ").replace("，", " ").replace("、", " ").replace("；", " ")
    text = re.sub(r"\d+\s*[\.、．]?\s*", " ", text)
    text = re.sub(r"[A-HＡ-Ｈ]\s*[\.、．\)]\s*", " ", text)

    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\-]{2,}", text)
    keywords: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        if token in _RETRIEVAL_BOILERPLATE:
            continue
        if token.startswith(("第", "选项", "答案")):
            continue
        if token not in seen:
            keywords.append(token)
            seen.add(token)

    # 优先保留更像领域关键词的短语，避免长题干把检索冲散
    keywords = sorted(
        keywords,
        key=lambda t: (len(t) < 4, len(t)),
    )

    if not keywords:
        return question

    # 限制长度，避免 query 过长导致全文检索稀释
    return " ".join(keywords[:12])


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

    for line in rest:
        option_match = _OPTION_RE.match(line)
        if option_match:
            saw_labeled_option = True
            options.append({
                "label": _normalize_option_label(option_match.group(1)),
                "text": option_match.group(2).strip(),
            })
            continue

        if saw_labeled_option and options:
            options[-1]["text"] = f"{options[-1]['text']} {line}".strip()
        else:
            stem_extra.append(_strip_answer_key(line))

    if not options and stem_extra:
        unlabeled = [item for item in stem_extra if item]
        if 2 <= len(unlabeled) <= 8:
            options = [
                {"label": _OPTION_LETTERS[idx], "text": text}
                for idx, text in enumerate(unlabeled)
            ]
            stem_extra = []

    if stem_extra:
        stem = f"{stem} {' '.join(stem_extra)}".strip()

    question_type = "choice" if options else "unknown"
    if options and answer_key:
        question_type = "multi_choice" if len(answer_key) > 1 else "choice"
    if not options and (answer_key in {"对", "错"} or re.search(r"(对还是错|对吗|错吗|判断|是否正确|是否错误)", stem)):
        question_type = "judge"

    return {
        "display_no": display_no,
        "question": stem,
        "options": options,
        "question_type": question_type,
        "answer_key": answer_key,
    }


def extract_objective_questions(filename: str, data: bytes) -> list[dict[str, Any]]:
    lines = _load_word_lines(filename, data)
    blocks = _split_question_blocks(lines)
    questions: list[dict[str, Any]] = []
    for idx, block in enumerate(blocks, start=1):
        item = _parse_question_block(block, idx)
        if item and item["question"]:
            questions.append(item)
    if not questions:
        raise ValueError("未从文档中识别出客观题，请检查题号或选项格式")
    return questions


def _format_context_section(section: dict) -> str:
    page_idx = section.get("page_idx")
    page_text = f" (第{page_idx + 1}页)" if isinstance(page_idx, int) and page_idx >= 0 else ""
    return f"[{section.get('doc_id', '')} §{section.get('number', '')}{page_text}] {section.get('title', '')}"


def _infer_objective_answer(text: str, question_type: str, option_labels: list[str]) -> str:
    normalized = _normalize_option_label(text)
    if question_type == "judge":
        normalized = _clean_reason_text(text)
        if "对" in normalized and "错" not in normalized[:2]:
            return "对"
        if "错" in normalized:
            return "错"

    labels = _choice_labels(option_labels)
    if not labels:
        labels = list(_OPTION_LETTERS[:8])

    if question_type == "multi_choice":
        matches = _extract_multi_choice_labels(text, labels)
        if matches:
            return "".join(matches)

    hint = _ANSWER_HINT_RE.search(text or "")
    if hint:
        hinted = _normalize_option_label(hint.group(1))
        if question_type == "multi_choice":
            hinted_multi = "".join(ch for ch in hinted if ch in labels)
            if hinted_multi:
                return hinted_multi
        elif hinted in labels:
            return hinted
        elif hinted in {"对", "错"}:
            return hinted

    for label in labels:
        if re.search(rf"(?<![A-Z0-9Ａ-Ｈ]){re.escape(label)}(?![A-Z0-9Ａ-Ｈ])", normalized):
            return label
        if normalized.startswith(label):
            return label

    return ""


def _normalize_support_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
    return text


def _score_option_support(context: str, option_text: str) -> int:
    """
    粗粒度证据支持度评分。
    通过完整短语命中和关键词重合来判断选项与证据的贴合程度。
    """
    ctx = _normalize_support_text(context)
    opt = _normalize_support_text(option_text)
    if not opt:
        return 0

    score = 0
    if opt in ctx:
        score += max(len(opt), 8)

    terms = []
    seen: set[str] = set()
    for token in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\-]{2,}", option_text):
        if token in seen:
            continue
        seen.add(token)
        if token in _RETRIEVAL_BOILERPLATE:
            continue
        if token.startswith(("第", "选项", "答案")):
            continue
        terms.append(token)

    for term in terms:
        if term in ctx:
            score += len(term) * 2

    return score


def _apply_choice_support_override(
    context: str,
    options: list[dict[str, str]],
    predicted_answer: str,
    reason: str,
) -> tuple[str, str]:
    if not options:
        return predicted_answer, reason

    labels = [opt.get("label", "").strip().upper() for opt in options]

    scores: dict[str, int] = {}
    for opt in options:
        label = opt.get("label", "").strip().upper()
        if not label:
            continue
        scores[label] = _score_option_support(context, opt.get("text", ""))

    if not scores:
        return predicted_answer, reason

    best_label = max(scores, key=scores.get)
    best_score = scores[best_label]
    ranked_scores = sorted(scores.values(), reverse=True)
    second_score = ranked_scores[1] if len(ranked_scores) > 1 else 0
    chosen_score = scores.get(predicted_answer, 0)

    if predicted_answer not in labels:
        if best_score > 0 and best_score >= second_score + 2:
            note = f"（根据证据支持度推断为 {best_label}）"
            return best_label, (reason + note).strip() if reason else note
        return predicted_answer, reason

    if best_label != predicted_answer and best_score >= chosen_score + 2:
        note = f"（根据证据支持度纠正为 {best_label}）"
        return best_label, (reason + note).strip() if reason else note

    return predicted_answer, reason


def _infer_answer_from_option_content(
    text: str,
    question_type: str,
    options: list[dict[str, str]],
) -> str:
    if question_type not in {"choice", "multi_choice"} or not text or not options:
        return ""

    normalized_text = _normalize_support_text(text)
    if not normalized_text:
        return ""

    exact_matches: list[str] = []
    scores: dict[str, int] = {}
    for opt in options:
        label = opt.get("label", "").strip().upper()
        option_text = opt.get("text", "")
        if not label or not option_text:
            continue
        normalized_option = _normalize_support_text(option_text)
        if normalized_option and normalized_option in normalized_text:
            exact_matches.append(label)
        scores[label] = _score_option_support(text, option_text)

    if question_type == "multi_choice":
        if len(exact_matches) > 1:
            return "".join(dict.fromkeys(exact_matches))
        positives = [label for label, score in scores.items() if score >= 6]
        if len(positives) > 1:
            return "".join(dict.fromkeys(positives))
        return ""

    if len(exact_matches) == 1:
        return exact_matches[0]

    if not scores:
        return ""

    best_label = max(scores, key=scores.get)
    ranked_scores = sorted(scores.values(), reverse=True)
    best_score = ranked_scores[0]
    second_score = ranked_scores[1] if len(ranked_scores) > 1 else 0
    if best_score > 0 and best_score >= second_score + 2:
        return best_label
    return ""


def _collect_objective_terms(question: str, options: list[dict[str, str]]) -> list[str]:
    text = f"{question}\n" + "\n".join(opt.get("text", "") for opt in options if opt.get("text"))
    text = re.sub(r"[（）()【】\[\]？?：:。！，,、；;]", " ", text)
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\-]{2,}", text)

    terms: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in _RETRIEVAL_BOILERPLATE:
            continue
        if token.startswith(("第", "选项", "答案")):
            continue
        if token not in seen:
            seen.add(token)
            terms.append(token)
    return terms[:24]


def _merge_unique_sections(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for section in group:
            chunk_id = section.get("chunk_id")
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            merged.append(section)
    return merged


def _expand_objective_graph_neighbors(driver: Driver, seed_sections: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    chunk_ids = [section.get("chunk_id") for section in seed_sections if section.get("chunk_id")]
    if not chunk_ids:
        return []

    with driver.session() as session:
        result = session.run(
            """
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION]-(nb:Section)
            OPTIONAL MATCH (p:Section)-[:HAS_SUBSECTION]->(s)
            WITH collect(DISTINCT nb) + collect(DISTINCT p) AS related
            UNWIND related AS sec
            WITH DISTINCT sec
            WHERE sec IS NOT NULL
            RETURN sec.chunk_id AS chunk_id,
                   sec.doc_id AS doc_id,
                   sec.number AS number,
                   sec.title AS title,
                   sec.content AS content,
                   sec.page_idx AS page_idx,
                   sec.bbox AS bbox,
                   sec.seq_index AS seq_index
            LIMIT $limit
            """,
            chunk_ids=chunk_ids[:6],
            limit=limit,
        )
        return [dict(row) for row in result]


def _expand_objective_local_neighbors(driver: Driver, seed_sections: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    chunk_ids = [section.get("chunk_id") for section in seed_sections if section.get("chunk_id")]
    if not chunk_ids:
        return []

    with driver.session() as session:
        result = session.run(
            """
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            MATCH (nb:Section {doc_id: s.doc_id})
            WHERE nb.chunk_id <> s.chunk_id
              AND nb.seq_index IS NOT NULL
              AND s.seq_index IS NOT NULL
              AND abs(nb.seq_index - s.seq_index) <= 2
            RETURN DISTINCT nb.chunk_id AS chunk_id,
                            nb.doc_id AS doc_id,
                            nb.number AS number,
                            nb.title AS title,
                            nb.content AS content,
                            nb.page_idx AS page_idx,
                            nb.bbox AS bbox,
                            nb.seq_index AS seq_index
            LIMIT $limit
            """,
            chunk_ids=chunk_ids[:6],
            limit=limit,
        )
        return [dict(row) for row in result]


def _score_objective_section(
    section: dict[str, Any],
    terms: list[str],
    ft_score_map: dict[str, float],
    doc_density: dict[str, int],
) -> float:
    chunk_id = section.get("chunk_id", "")
    doc_id = section.get("doc_id", "")
    title = section.get("title", "") or ""
    content = section.get("content", "") or ""
    title_norm = _normalize_support_text(title)
    content_norm = _normalize_support_text(content)

    score = float(ft_score_map.get(chunk_id, 0.0))
    score += doc_density.get(doc_id, 0) * 1.5

    for term in terms:
        normalized_term = _normalize_support_text(term)
        if not normalized_term:
            continue
        if normalized_term in title_norm:
            score += max(4.0, len(term) * 2.0)
        if normalized_term in content_norm:
            score += max(2.0, len(term) * 1.2)

    return score


def _retrieve_objective_sections(
    question: str,
    options: list[dict[str, str]],
    strategy: str,
    top_k: int,
    driver: Driver,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    do_retrieval = _get_do_retrieval()
    candidate_k = max(top_k * 4, 12)
    stem_query = _build_objective_retrieval_query(question, [])
    merged_sections: list[dict[str, Any]] = []
    ft_score_map: dict[str, float] = {}

    retrieval_plans = [(stem_query, strategy, False, 0.5)]
    if strategy != "graph_augmented":
        retrieval_plans.append((stem_query, "graph_augmented", False, 0.5))
    if options:
        fallback_query = _build_objective_retrieval_query(question, options)
        retrieval_plans.append((fallback_query, "parallel", True, 0.6))

    for query, plan_strategy, use_hyde, hyde_alpha in retrieval_plans:
        sections, local_scores = do_retrieval(
            driver,
            query,
            plan_strategy,
            candidate_k,
            use_hyde=use_hyde,
            hyde_alpha=hyde_alpha,
        )
        merged_sections = _merge_unique_sections(merged_sections, sections)
        for chunk_id, score in local_scores.items():
            ft_score_map[chunk_id] = max(ft_score_map.get(chunk_id, float("-inf")), score)

    expanded_graph = _expand_objective_graph_neighbors(driver, merged_sections)
    expanded_local = _expand_objective_local_neighbors(driver, merged_sections)
    merged_sections = _merge_unique_sections(merged_sections, expanded_graph, expanded_local)

    terms = _collect_objective_terms(question, options)
    doc_density: dict[str, int] = {}
    for section in merged_sections[:candidate_k]:
        doc_id = section.get("doc_id", "")
        if doc_id:
            doc_density[doc_id] = doc_density.get(doc_id, 0) + 1

    ranked = sorted(
        merged_sections,
        key=lambda section: _score_objective_section(section, terms, ft_score_map, doc_density),
        reverse=True,
    )
    return ranked[: max(top_k * 2, 8)], ft_score_map


def _parse_objective_llm_response(raw: str, question_type: str, option_labels: list[str]) -> tuple[str, str]:
    text = (raw or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            payload = json.loads(m.group())
            answer = _clean_reason_text(str(payload.get("final_answer", "")).strip())
            reason = _clean_reason_text(str(payload.get("reason", "")).strip())
            parsed_answer = _infer_objective_answer(answer, question_type, option_labels)
            if parsed_answer:
                return _normalize_option_label(parsed_answer), reason or text
            inferred = _infer_objective_answer(reason or text, question_type, option_labels)
            if inferred:
                return _normalize_option_label(inferred), reason or text
            return "", reason or _clean_reason_text(text)
        except Exception:
            pass

    # 宽松解析：兼容 {"final_answer":"C",reason:"..."} 这类不规范返回
    answer_match = re.search(
        r'["\']?final_answer["\']?\s*:\s*["\']?(?P<answer>[^,}\]\n]+)',
        text,
        re.IGNORECASE,
    )
    reason_match = re.search(
        r'["\']?reason["\']?\s*:\s*["\']?(?P<reason>.*?)(?:["\']\s*[}\]]|[}\]]\s*$)',
        text,
        re.DOTALL,
    )
    if answer_match:
        answer = _clean_reason_text(answer_match.group("answer").replace("√", "对").replace("×", "错"))
        parsed_answer = _infer_objective_answer(answer, question_type, option_labels)
        reason = _clean_reason_text(reason_match.group("reason")) if reason_match else _clean_reason_text(text)
        if parsed_answer:
            return _normalize_option_label(parsed_answer), reason or text
        inferred = _infer_objective_answer(reason or text, question_type, option_labels)
        if inferred:
            return _normalize_option_label(inferred), reason or text
        return "", reason or _clean_reason_text(text)

    inferred = _infer_objective_answer(text, question_type, option_labels)
    if inferred:
        return _normalize_option_label(inferred), text
    return "", _clean_reason_text(text)


def _answer_objective_question(
    question: str,
    options: list[dict[str, str]],
    question_type: str,
    answer_key: str,
    strategy: str,
    top_k: int,
    driver: Driver,
) -> dict[str, Any]:
    sections, ft_score_map = _retrieve_objective_sections(question, options, strategy, top_k, driver)

    source_refs = [
        f"{s['doc_id']} §{s.get('number') or ''}"
        for s in sections
    ]

    if not sections:
        return {
            "predicted_answer": "",
            "reason": "未检索到相关章节",
            "source_refs": [],
            "raw_response": "",
        }

    context = "\n\n".join(
        f"{_format_context_section(s)}\n{s['content']}"
        for s in sections
    )
    option_text = "\n".join(f"{opt['label']}. {opt['text']}" for opt in options) if options else ""
    option_block = f"## 选项\n{option_text}\n\n" if option_text else ""
    answer_mode = _answer_mode_from_key(answer_key)
    if answer_mode == "multi_choice":
        answer_format = "所有正确选项字母，按字母升序连接，例如 BCD"
    elif answer_mode == "single_choice":
        answer_format = "一个正确选项字母"
    elif answer_mode == "judge":
        answer_format = "对/错"
    else:
        answer_format = "简短最终答案"
    messages = [
        {
            "role": "system",
            "content": (
                "你是航空制造工艺规范专家。请根据提供的规范内容回答客观题。"
                "如果证据不足，不要编造。请输出一个 JSON 对象："
                '{"final_answer":"...","reason":"..."}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"## 相关规范内容\n{context}\n\n"
                f"## 题目\n{question}\n\n"
                f"{option_block}"
                f"## 题型\n{('多选题' if answer_mode == 'multi_choice' else '单选题' if answer_mode == 'single_choice' else '判断题' if answer_mode == 'judge' else '简答题')}\n\n"
                f"说明：{('题目括号中的答案键表明这是多选题，final_answer 必须输出全部正确选项字母并按字母升序拼接' if answer_mode == 'multi_choice' else 'final_answer 只输出一个选项字母' if answer_mode == 'single_choice' else 'final_answer 只输出对或错' if answer_mode == 'judge' else 'final_answer 只输出简短答案')}\n\n"
                f"请给出最终答案，final_answer 仅输出 {answer_format}。"
            ),
        },
    ]
    raw = get_llm_service().chat(messages, timeout=60)
    predicted_answer, reason = _parse_objective_llm_response(raw, question_type, [opt["label"] for opt in options])
    if not predicted_answer and options:
        predicted_answer = _infer_answer_from_option_content(reason or raw, question_type, options)
    if question_type == "choice" and options and context:
        predicted_answer, reason = _apply_choice_support_override(context, options, predicted_answer, reason)
    return {
        "predicted_answer": predicted_answer,
        "reason": reason,
        "source_refs": source_refs,
        "raw_response": raw,
    }


async def _run_task(
    task_id: str,
    questions: list[dict[str, Any]],
    strategy: str,
    top_k: int,
    driver: Driver,
) -> None:
    task = _tasks[task_id]
    task["status"] = "running"
    task["started_at"] = _now()
    results: list[dict[str, Any]] = []

    try:
        for idx, item in enumerate(questions, start=1):
            result = await asyncio.to_thread(
                _answer_objective_question,
                item["question"],
                item["options"],
                item["question_type"],
                item.get("answer_key", ""),
                strategy,
                top_k,
                driver,
            )
            row = {
                "display_no": item["display_no"],
                "question": item["question"],
                "options": item["options"],
                "question_type": item["question_type"],
                "predicted_answer": result["predicted_answer"],
                "reason": result["reason"],
                "source_refs": result["source_refs"],
            }
            results.append(row)

            task["completed"] = idx
            task["current_question"] = item["question"][:80]
            task["results_preview"] = results[-20:]
            await _persist_task(task)
            await asyncio.sleep(0)

        task["status"] = "completed"
        task["finished_at"] = _now()
        task["results"] = results
        task["results_preview"] = results[:50]
        task["summary"] = {
            "total": len(results),
            "choice_count": sum(1 for row in results if row["options"]),
            "judge_count": sum(1 for row in results if row["question_type"] == "judge"),
        }
        await _persist_task(task)
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = _now()
        task["error"] = str(exc)
        await _persist_task(task)


async def start_objective_doc_eval(
    filename: str,
    data: bytes,
    strategy: str,
    top_k: int,
    driver: Driver,
) -> dict[str, Any]:
    questions = extract_objective_questions(filename, data)
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {
        "task_id": task_id,
        "filename": filename,
        "status": "queued",
        "strategy": strategy,
        "top_k": top_k,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "total": len(questions),
        "completed": 0,
        "current_question": "",
        "error": "",
        "summary": None,
        "results_preview": [],
        "results": [],
    }
    await _persist_task(_tasks[task_id])
    asyncio.create_task(_run_task(task_id, questions, strategy, top_k, driver))
    return get_objective_task(task_id)


def get_objective_task(task_id: str) -> dict[str, Any]:
    task = _tasks.get(task_id)
    if not task:
        raise KeyError(task_id)
    return task


async def get_objective_task_record(task_id: str) -> dict[str, Any]:
    task = _tasks.get(task_id)
    if task:
        return task
    return await _load_task_from_db(task_id)


def _render_task_csv(task: dict[str, Any]) -> str:
    if task["status"] != "completed":
        raise ValueError("任务尚未完成，暂时不能导出")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["display_no", "question_type", "question", "options", "predicted_answer", "reason", "source_refs"])
    for row in task["results"]:
        options_text = " | ".join(f"{opt['label']}. {opt['text']}" for opt in row["options"])
        writer.writerow([
            row["display_no"],
            row["question_type"],
            row["question"],
            options_text,
            row["predicted_answer"],
            row["reason"],
            " | ".join(row["source_refs"]),
        ])
    return buf.getvalue()


async def export_objective_task_csv_async(task_id: str) -> str:
    task = await get_objective_task_record(task_id)
    return _render_task_csv(task)


def export_objective_task_csv(task_id: str) -> str:
    task = get_objective_task(task_id)
    return _render_task_csv(task)
