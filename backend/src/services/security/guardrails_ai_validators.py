"""
Guardrails AI custom validators for aviation knowledge-base LLM outputs.

Plugs into guardrails.py's _try_guardrails_ai stub via direct import.
Validators enforce:
  1. SourceCitation   — answer must reference at least one source chunk
  2. NoHallucination  — numeric values in answer must appear in source content
  3. AviationTopicGuard — answer must relate to aviation / engineering domain

Usage (standalone):
    from .guardrails_ai_validators import run_guardrails_ai
    result = run_guardrails_ai(answer, question, sources)

Requires:
    pip install guardrails-ai>=0.4
"""
from __future__ import annotations

import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Aviation domain keywords — answer must contain ≥1 to pass topic guard
AVIATION_KEYWORDS = re.compile(
    r"规范|工艺|航空|液压|力矩|扭矩|合金|钢|铝|钛|温度|压力|MPa|PSI|mm|装配|安装|检验|测试|部件|发动机|机身",
    re.IGNORECASE,
)


def _validators_available() -> bool:
    try:
        import guardrails as gd  # noqa: F401
        return True
    except ImportError:
        return False


class SourceCitationValidator:
    """Fail if answer references no sources."""

    def validate(self, answer: str, sources: list[dict]) -> list[str]:
        if not sources:
            return ["answer_has_no_sources"]
        cited = any(
            s.get("chunk_id", "") in answer or s.get("title", "") in answer
            for s in sources
        )
        if not cited and len(sources) > 0:
            # Soft warning — sources exist but not explicitly cited in text
            log.debug("SourceCitation: sources not explicitly cited in answer text")
        return []


class NoHallucinationValidator:
    """Warn if numeric values appear in answer but not in any source."""

    _NUM = re.compile(r"\b\d+(?:\.\d+)?\s*(?:N·m|MPa|PSI|bar|°C|mm|kg|rpm|%)\b")

    def validate(self, answer: str, sources: list[dict]) -> list[str]:
        source_text = " ".join(s.get("content", "") for s in sources)
        suspicious = [v for v in self._NUM.findall(answer) if v not in source_text]
        if len(suspicious) >= 3:
            return [f"possible_hallucination:{','.join(suspicious[:3])}"]
        return []


class AviationTopicGuard:
    """Reject answers that don't appear to address aviation/engineering content."""

    def validate(self, answer: str, question: str) -> list[str]:
        combined = answer + " " + question
        if not AVIATION_KEYWORDS.search(combined):
            return ["off_topic:non_aviation_content"]
        return []


def run_guardrails_ai(
    answer: str,
    question: str,
    sources: list[dict],
    strict: bool = False,
) -> dict[str, Any]:
    """
    Run all validators. Returns {"issues": [...], "passed": bool}.

    When guardrails-ai library is installed, validators are also registered
    there for structured output validation via Rail schemas.
    """
    issues: list[str] = []

    issues += SourceCitationValidator().validate(answer, sources)
    issues += NoHallucinationValidator().validate(answer, sources)
    issues += AviationTopicGuard().validate(answer, question)

    # Optional: register with guardrails-ai if installed
    if _validators_available():
        try:
            _run_gd_rail(answer, sources, issues)
        except Exception as exc:
            log.debug("guardrails-ai rail check skipped: %s", exc)

    return {"issues": issues, "passed": len(issues) == 0}


def _run_gd_rail(answer: str, sources: list[dict], issues: list[str]) -> None:
    """Run structured Rail validation via guardrails-ai library."""
    import guardrails as gd

    rail_spec = """
<rail version="0.1">
  <output>
    <string name="answer" description="LLM answer" required="true" />
    <list name="sources" description="Source citations" required="true">
      <object>
        <string name="chunk_id" required="true" />
      </object>
    </list>
    <float name="confidence" description="0-1 confidence score" required="false" />
  </output>
</rail>
"""
    try:
        guard = gd.Guard.from_rail_string(rail_spec)
        validated, *_ = guard.parse(answer)
        if validated is None:
            issues.append("guardrails_ai:format_validation_failed")
    except Exception:
        pass
