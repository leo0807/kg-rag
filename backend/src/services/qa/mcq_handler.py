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
    has_options = bool(re.search(r'[（(][A-Da-d][）)]|\n[A-D][\.．\s]', q))

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

_TOPIC_PREFIXES = ("密封", "涂层", "铆接", "焊接", "热处理", "复合材料", "粘结")


def parse_options_from_question(question: str) -> dict[str, str]:
    """Extract {letter: text} from bracket '（A）' or newline 'A ' style questions."""
    # Try bracket format first
    matches = re.findall(r'[（(]([A-Da-d])[）)]\s*(.*?)(?=[（(][A-Da-d][）)]|$)', question, re.DOTALL)
    if matches:
        return {m[0].upper(): m[1].strip() for m in matches}
    # Fallback: newline-separated "A content\nB content"
    matches = re.findall(r'\n([A-Da-d])[\.．\s]\s*(.*?)(?=\n[A-Da-d][\.．\s]|$)', question, re.DOTALL)
    return {m[0].upper(): m[1].strip() for m in matches}


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
    stem = re.sub(r'(\n[A-Da-d]\s+.*|[（(][A-Da-d][）)].+)', '', question, flags=re.DOTALL).strip() or question

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
