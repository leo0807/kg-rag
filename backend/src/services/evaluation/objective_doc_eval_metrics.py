from __future__ import annotations

import re
from typing import Any

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
_OPTION_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _normalize_support_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text)


def _normalize_option_label(label: str) -> str:
    return label.strip().upper().translate(str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH"))


def _choice_labels(option_labels: list[str]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for label in option_labels:
        normalized = _normalize_option_label(label)
        if normalized in _OPTION_LETTERS and normalized not in seen:
            labels.append(normalized)
            seen.add(normalized)
    return labels


def _infer_objective_answer(text: str, question_type: str, option_labels: list[str]) -> str:
    normalized = _normalize_option_label(text)
    if question_type == "judge":
        normalized = text.strip()
        if "对" in normalized and "错" not in normalized[:2]:
            return "对"
        if "错" in normalized:
            return "错"

    labels = _choice_labels(option_labels) or list(_OPTION_LETTERS[:8])
    if question_type == "multi_choice":
        matches: list[str] = []
        compact = _CHOICE_LABEL_RE.search(_normalize_option_label(text or ""))
        if compact:
            candidate = compact.group(1)
            if len(candidate) > 1:
                for ch in candidate:
                    if ch in labels and ch not in matches:
                        matches.append(ch)
                if len(matches) > 1:
                    return "".join(matches)
        for ch in _SINGLE_CHOICE_LABEL_RE.findall(_normalize_option_label(text or "")):
            if ch in labels and ch not in matches:
                matches.append(ch)
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


def _score_option_support(context: str, option_text: str) -> int:
    ctx = _normalize_support_text(context)
    opt = _normalize_support_text(option_text)
    if not opt:
        return 0
    score = max(len(opt), 8) if opt in ctx else 0
    seen: set[str] = set()
    for token in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\-]{2,}", option_text):
        if token in seen or token in _RETRIEVAL_BOILERPLATE or token.startswith(("第", "选项", "答案")):
            continue
        seen.add(token)
        if token in ctx:
            score += len(token) * 2
    return score


def _apply_choice_support_override(
    context: str, options: list[dict[str, str]], predicted_answer: str, reason: str,
) -> tuple[str, str]:
    if not options:
        return predicted_answer, reason
    labels = [opt.get("label", "").strip().upper() for opt in options]
    scores = {opt.get("label", "").strip().upper(): _score_option_support(context, opt.get("text", "")) for opt in options if opt.get("label")}
    if not scores:
        return predicted_answer, reason
    best_label = max(scores, key=scores.get)  # type: ignore[arg-type]
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


def _infer_answer_from_option_content(text: str, question_type: str, options: list[dict[str, str]]) -> str:
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
    best_label = max(scores, key=scores.get)  # type: ignore[arg-type]
    ranked_scores = sorted(scores.values(), reverse=True)
    best_score = ranked_scores[0]
    second_score = ranked_scores[1] if len(ranked_scores) > 1 else 0
    return best_label if best_score > 0 and best_score >= second_score + 2 else ""


def _collect_objective_terms(question: str, options: list[dict[str, str]]) -> list[str]:
    text = f"{question}\n" + "\n".join(opt.get("text", "") for opt in options if opt.get("text"))
    text = re.sub(r"[（）()【】\[\]？?：:。！，,、；;]", " ", text)
    terms: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\-]{2,}", text):
        if token in _RETRIEVAL_BOILERPLATE or token.startswith(("第", "选项", "答案")):
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


def _format_context_section(section: dict) -> str:
    page_idx = section.get("page_idx")
    page_text = f" (第{page_idx + 1}页)" if isinstance(page_idx, int) and page_idx >= 0 else ""
    return f"[{section.get('doc_id', '')} §{section.get('number', '')}{page_text}] {section.get('title', '')}"


def _score_objective_section(
    section: dict[str, Any], terms: list[str], ft_score_map: dict[str, float], doc_density: dict[str, int],
) -> float:
    chunk_id = section.get("chunk_id", "")
    doc_id = section.get("doc_id", "")
    title_norm = _normalize_support_text(section.get("title", "") or "")
    content_norm = _normalize_support_text(section.get("content", "") or "")
    score = float(ft_score_map.get(chunk_id, 0.0)) + doc_density.get(doc_id, 0) * 1.5
    for term in terms:
        normalized_term = _normalize_support_text(term)
        if not normalized_term:
            continue
        if normalized_term in title_norm:
            score += max(4.0, len(term) * 2.0)
        if normalized_term in content_norm:
            score += max(2.0, len(term) * 1.2)
    return score
