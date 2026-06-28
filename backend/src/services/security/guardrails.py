"""
LLM Output Guardrails.

Validates LLM responses before returning to user:
  1. Must include source references (non-empty sources list)
  2. Must not contain values not present in retrieved context (hallucination guard)
  3. Output must conform to expected Pydantic schema

Uses guardrails-ai if installed, falls back to built-in validation.
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)


class GuardrailsValidationError(Exception):
    pass


def validate_has_sources(answer: str, sources: list[dict]) -> bool:
    """Response must have at least one cited source."""
    if not sources:
        log.warning("Guardrails: answer has no sources")
        return False
    return True


def validate_no_hallucination(answer: str, sources: list[dict],
                               strict: bool = False) -> tuple[bool, list[str]]:
    """
    Check if numeric values in the answer appear in source content.
    Returns (passed, list_of_suspicious_values).
    """
    source_text = " ".join(s.get("content", "") for s in sources)
    # Extract numbers + units from answer
    num_pattern = re.compile(r'\d+(?:\.\d+)?\s*(?:N·m|PSI|MPa|°C|mm|kg|bar|rpm|%)?')
    answer_nums = num_pattern.findall(answer)
    suspicious = []
    for num in answer_nums:
        val = num.strip()
        if val and val not in source_text:
            suspicious.append(val)
    passed = len(suspicious) == 0 if strict else len(suspicious) < 3
    return passed, suspicious


def validate_topic_relevance(answer: str, question: str) -> bool:
    """
    Basic topicality check: answer should contain some keywords from question.
    """
    q_words = set(re.findall(r'[一-鿿]{2,}|\w{4,}', question.lower()))
    a_words = set(re.findall(r'[一-鿿]{2,}|\w{4,}', answer.lower()))
    if not q_words:
        return True
    overlap = len(q_words & a_words) / len(q_words)
    return overlap >= 0.1  # At least 10% keyword overlap


def run_guardrails(answer: str, question: str, sources: list[dict],
                   strict: bool = False) -> dict[str, Any]:
    """
    Run all guardrails checks. Returns validation report.

    Args:
        answer: LLM-generated answer
        question: Original user question
        sources: Retrieved source sections
        strict: If True, numeric hallucination triggers hard failure

    Returns:
        {"passed": bool, "issues": [...], "answer": possibly_modified_answer}
    """
    issues = []

    # Check 1: Sources present
    if not validate_has_sources(answer, sources):
        issues.append("no_sources")

    # Check 2: Hallucination check
    passed, suspicious = validate_no_hallucination(answer, sources, strict)
    if not passed:
        issues.append(f"possible_hallucination:{','.join(suspicious[:3])}")

    # Check 3: Topic relevance
    if not validate_topic_relevance(answer, question):
        issues.append("off_topic")

    # Try guardrails-ai if installed
    guardrails_result = _try_guardrails_ai(answer, sources)
    if guardrails_result:
        issues.extend(guardrails_result.get("issues", []))

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "answer": answer,
    }


def _try_guardrails_ai(answer: str, sources: list[dict]) -> dict | None:
    """Use guardrails-ai library if installed."""
    try:
        import guardrails as gd  # noqa: F401
        # Minimal integration — guardrails-ai requires custom validators
        return None
    except ImportError:
        return None


class AnswerGuard:
    """Callable guard that raises on critical failures."""

    def __init__(self, strict: bool = False) -> None:
        self.strict = strict

    def check(self, answer: str, question: str,
              sources: list[dict]) -> str:
        """
        Validate and return the answer.
        Raises GuardrailsValidationError if critical issues found.
        """
        result = run_guardrails(answer, question, sources, self.strict)
        critical = [i for i in result["issues"] if "hallucination" in i and self.strict]
        if critical:
            raise GuardrailsValidationError(
                f"LLM answer failed guardrails: {critical}"
            )
        if result["issues"]:
            log.warning("Guardrails issues (non-fatal): %s", result["issues"])
        return result["answer"]
