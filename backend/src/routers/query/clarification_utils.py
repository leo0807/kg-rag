from __future__ import annotations

import json

from ...services.agent.clarification import ClarificationDetector

CLARIFICATION_MESSAGE = "您的问题有些宽泛，请选择您想了解的方向："


async def detect_clarification(question: str, driver) -> dict:
    detector = ClarificationDetector()
    return await detector.needs_clarification(question, driver)


def build_clarification_payload(
    question: str,
    clarification: dict,
) -> dict:
    return {
        "type": "clarification_needed",
        "message": CLARIFICATION_MESSAGE,
        "options": clarification.get("clarification_options", []),
        "original_question": question,
        "answer": "",
        "sources": [],
    }


def build_clarification_event(question: str, clarification: dict) -> str:
    return f"data: {json.dumps(build_clarification_payload(question, clarification), ensure_ascii=False)}\n\n"
