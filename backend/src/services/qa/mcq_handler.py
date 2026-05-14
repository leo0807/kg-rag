from __future__ import annotations

import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)


class QuestionType(Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    MULTIPLE_SELECT = "multiple_select"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    OPEN = "open"


_LABELS: dict[QuestionType, str] = {
    QuestionType.MULTIPLE_CHOICE: "单选题",
    QuestionType.MULTIPLE_SELECT: "多选题",
    QuestionType.TRUE_FALSE: "判断题",
    QuestionType.FILL_BLANK: "填空题",
    QuestionType.SHORT_ANSWER: "简答题",
    QuestionType.OPEN: "问答题",
}


def detect_question_type(question: str) -> QuestionType:
    q = question.strip()
    # Detect options in bracket format （A） or newline format \nA / \nA.
    has_options = bool(re.search(r'[（(][A-Ha-h][）)]|\n[A-H][\.．\s]', q))

    if any(kw in q for kw in ("多选", "以下哪些", "下列哪些", "哪些是")) and has_options:
        return QuestionType.MULTIPLE_SELECT
    if has_options or any(kw in q for kw in ("单选", "下列哪一项", "以下哪个", "下列哪个", "哪一项正确", "哪一项是")):
        return QuestionType.MULTIPLE_CHOICE
    if any(kw in q for kw in ("判断", "是否正确", "对还是错", "正确还是错误", "（对）", "（错）")):
        return QuestionType.TRUE_FALSE
    if any(kw in q for kw in ("填写", "填入", "填空", "______", "（　）", "(__)")):
        return QuestionType.FILL_BLANK
    if any(kw in q for kw in ("简述", "简要说明", "简要描述", "列举", "列出")):
        return QuestionType.SHORT_ANSWER
    return QuestionType.OPEN


def get_type_label(qt: QuestionType) -> str:
    return _LABELS.get(qt, "问答题")


# ── MCQ option parsing & keyword verification ────────────────────────────────

_OPTION_STOP: frozenset[str] = frozenset({
    "以上", "以下", "包括", "正确", "错误", "所有", "以及", "都是", "都不", "选项",
})
_OPTION_BLOCK_RE = re.compile(
    r'(?:^|\n)\s*([A-Ha-h])\s*[、．.）\)]\s*(.+?)(?=\n\s*[A-Ha-h]\s*[、．.）\)]|$)',
    re.MULTILINE | re.DOTALL,
)
_OPTION_INLINE_RE = re.compile(
    r'([A-Ha-h])\s*[、．.）\)\s]\s*(.+?)(?=\s+[A-Ha-h]\s*[、．.）\)\s]|$)',
    re.DOTALL,
)
_COMBO_MARKER_RE = re.compile(r'[①②③④⑤⑥⑦⑧]|[\-→]')

_TOPIC_PREFIXES = ("密封", "涂层", "铆接", "焊接", "热处理", "复合材料", "粘结")


def parse_options_from_question(question: str) -> dict[str, str]:
    """Extract {letter: text} from bracket or inline options, and drop non-answer candidates."""
    return split_question_and_options(question)[1]


def split_question_and_options(question: str) -> tuple[str, dict[str, str]]:
    text = question or ""
    matches = list(_OPTION_BLOCK_RE.finditer(text))
    if len(matches) >= 2:
        options = {m.group(1).upper(): m.group(2).strip() for m in matches}
        return (text[: matches[0].start()].strip() or text.strip(), identify_answer_options(options))
    matches = list(_OPTION_INLINE_RE.finditer(text))
    if len(matches) >= 2:
        options = {m.group(1).upper(): m.group(2).strip() for m in matches}
        return (text[: matches[0].start()].strip() or text.strip(), identify_answer_options(options))
    matches = re.findall(r'[（(]([A-Ha-h])[）)]\s*(.*?)(?=[（(][A-Ha-h][）)]|$)', text, re.DOTALL)
    if len(matches) >= 2:
        options = {m[0].upper(): m[1].strip() for m in matches}
        first = re.search(r'[（(]([A-Ha-h])[）)]', text)
        stem = text[: first.start()].strip() if first else text.strip()
        return stem or text.strip(), identify_answer_options(options)
    return text.strip(), {}


def identify_answer_options(options: dict[str, str]) -> dict[str, str]:
    """Keep the real answer candidates when A-D are definitions and E-H are combinations."""
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


def clean_mcq_output(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("```json", "").replace("```", "")
    cleaned = cleaned.replace("\ufffd", "")
    return cleaned.strip()


def _normalize_option_label(label: str) -> str:
    return label.strip().upper().translate(str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH"))


def extract_answer_letter(llm_response: str, options: dict[str, str]) -> str:
    text = clean_mcq_output(llm_response)
    labels = list(options.keys())
    m = re.search(r"(?:答案|最终答案|answer|final_answer)\s*[:：=\s]*[【\[]?([A-HＡ-Ｈ])", text, re.IGNORECASE)
    if m:
        letter = _normalize_option_label(m.group(1))
        if letter in labels:
            return letter
    m = re.search(r'"answer"\s*:\s*"([A-HＡ-Ｈ])"', text, re.IGNORECASE)
    if m:
        letter = _normalize_option_label(m.group(1))
        if letter in labels:
            return letter
    normalized_text = re.sub(r"\s+", "", text)
    for letter, content in options.items():
        candidate = re.sub(r"\s+", "", content or "")
        if candidate and candidate in normalized_text:
            return letter
    return ""


def _extract_option_keywords(text: str, max_kws: int = 4) -> list[str]:
    words = re.findall(r'[一-鿿]{2,}', text)
    return [w for w in words if w not in _OPTION_STOP][:max_kws]


async def verify_options(
    question: str,
    options: dict[str, str],
    driver,
    doc_id: str = "",
    top_k: int = 3,
    stem_content: str = "",
) -> tuple[dict[str, float], str]:
    """Score each option via positive (stem content) + coverage (option-specific retrieval)."""
    import asyncio
    from ...routers.query.core import do_retrieval

    # Strip option text to get pure question stem
    stem, _ = split_question_and_options(question)

    # Retrieve stem content if not provided by caller
    if not stem_content:
        try:
            secs, _, _ = await asyncio.to_thread(
                do_retrieval, driver, stem, "parallel", 10, False, 0.5, doc_id, False
            )
            stem_content = " ".join(s.get("content", "") for s in secs)
        except Exception:
            pass

    option_scores: dict[str, float] = {}
    option_lines: list[str] = []

    async def _score(letter: str, opt_text: str) -> None:
        kws = _extract_option_keywords(opt_text)
        if not kws:
            option_scores[letter] = 0.0
            option_lines.append(f"选项{letter}（0.00）: 无关键词")
            return
        positive = sum(1 for kw in kws if kw in stem_content) / len(kws)
        try:
            opt_secs, _, _ = await asyncio.to_thread(
                do_retrieval, driver, f"{stem} {opt_text}", "parallel", top_k, False, 0.5, doc_id, False
            )
            opt_content = " ".join(s.get("content", "") for s in opt_secs)
        except Exception:
            opt_content = ""
        coverage = sum(1 for kw in kws if kw in opt_content) / len(kws)
        option_scores[letter] = round((positive + coverage) / 2, 2)
        # Show keyword hits only — no raw snippets to avoid OCR artifact injection
        kw_tags = [f"{kw}({'✓' if kw in opt_content else '✗'})" for kw in kws]
        option_lines.append(f"选项{letter}（{option_scores[letter]:.2f}）: {', '.join(kw_tags)}")

    await asyncio.gather(*[_score(l, c) for l, c in options.items()])
    logger.info("MCQ选项得分: %s", option_scores)

    option_lines.sort()
    return option_scores, "【选项验证（规范检索）】\n" + "\n".join(option_lines)


def build_mcq_question(question: str):
    from .mcq_elimination import build_mcq_question as _build_mcq_question
    return _build_mcq_question(question)


async def solve_mcq_with_elimination(*args, **kwargs):
    from .mcq_elimination import solve_mcq_with_elimination as _solve_mcq_with_elimination
    return await _solve_mcq_with_elimination(*args, **kwargs)
