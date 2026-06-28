"""
TruLens online scorer for production queries.

Runs as a background async task: after each production query returns its answer,
the scorer computes Groundedness + Answer Relevance and writes results to
PostgreSQL. Queries scoring below the thresholds are flagged for human review.

Usage (called from the query router after a successful response):
    from ..services.analytics.trulens_scorer import score_in_background
    score_in_background(query_id, question, answer, contexts)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

# Score thresholds below which queries are flagged for review
GROUNDEDNESS_THRESHOLD = float(os.getenv("TRULENS_GROUNDEDNESS_THRESHOLD", "0.5"))
RELEVANCE_THRESHOLD    = float(os.getenv("TRULENS_RELEVANCE_THRESHOLD", "0.5"))


# ---------------------------------------------------------------------------
# PostgreSQL helpers (uses the existing asyncpg pool via db module)
# ---------------------------------------------------------------------------

async def _ensure_table(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS trulens_scores (
            id              SERIAL PRIMARY KEY,
            query_id        TEXT NOT NULL,
            question        TEXT NOT NULL,
            groundedness    FLOAT,
            answer_relevance FLOAT,
            needs_review    BOOLEAN DEFAULT FALSE,
            scored_at       TIMESTAMPTZ NOT NULL
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trulens_query_id
        ON trulens_scores (query_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trulens_needs_review
        ON trulens_scores (needs_review) WHERE needs_review = TRUE
    """)


async def _write_score(
    query_id: str,
    question: str,
    groundedness: float | None,
    relevance: float | None,
    needs_review: bool,
) -> None:
    try:
        import asyncpg  # noqa: PLC0415

        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/kgrag",
        )
        conn = await asyncpg.connect(db_url)
        try:
            await _ensure_table(conn)
            await conn.execute(
                """
                INSERT INTO trulens_scores
                    (query_id, question, groundedness, answer_relevance,
                     needs_review, scored_at)
                VALUES ($1,$2,$3,$4,$5,$6)
                """,
                query_id,
                question,
                groundedness,
                relevance,
                needs_review,
                datetime.now(timezone.utc),
            )
        finally:
            await conn.close()
    except Exception as exc:
        log.warning("trulens_scorer: DB write failed: %s", exc)


# ---------------------------------------------------------------------------
# TruLens scoring (real when installed, fallback to LLM-based heuristic)
# ---------------------------------------------------------------------------

def _score_with_trulens(
    question: str,
    answer: str,
    contexts: list[str],
) -> tuple[float | None, float | None]:
    """Return (groundedness, answer_relevance) using TruLens."""
    from trulens_eval import Feedback, Tru  # noqa: PLC0415
    from trulens_eval.feedback.provider import OpenAI as TruOpenAI  # noqa: PLC0415

    provider = TruOpenAI()
    f_ground = (
        Feedback(provider.groundedness_measure_with_cot_reasons)
        .on("\n\n".join(contexts))
        .on_output()
    )
    f_rel = (
        Feedback(provider.relevance_with_cot_reasons)
        .on_input()
        .on_output()
    )
    g_score, _ = f_ground(contexts=contexts, response=answer)
    r_score, _ = f_rel(prompt=question, response=answer)
    return float(g_score), float(r_score)


async def _score_heuristic(
    question: str,
    answer: str,
    contexts: list[str],
) -> tuple[float | None, float | None]:
    """
    Lightweight LLM-based fallback when TruLens is not installed.
    Uses the existing LLM client (Claude) with a simple rubric prompt.
    """
    try:
        from ..ai.llm_client import get_llm_client  # noqa: PLC0415

        client = get_llm_client()
        context_text = "\n---\n".join(contexts[:3])
        prompt = (
            f"Rate the following answer on two dimensions (0.0-1.0 each):\n\n"
            f"QUESTION: {question}\n\n"
            f"CONTEXTS:\n{context_text}\n\n"
            f"ANSWER: {answer}\n\n"
            f"Respond with JSON only, e.g. {{\"groundedness\": 0.85, \"relevance\": 0.90}}.\n"
            f"groundedness = fraction of answer claims supported by contexts.\n"
            f"relevance = how well the answer addresses the question."
        )
        response = await client.complete(prompt, max_tokens=64)
        import json  # noqa: PLC0415

        scores = json.loads(response.strip())
        return float(scores.get("groundedness", 0.0)), float(scores.get("relevance", 0.0))
    except Exception as exc:
        log.debug("heuristic scorer failed: %s", exc)
        return None, None


async def _score_query(
    query_id: str,
    question: str,
    answer: str,
    contexts: list[str],
) -> None:
    groundedness: float | None = None
    relevance: float | None = None

    try:
        groundedness, relevance = _score_with_trulens(question, answer, contexts)
    except ImportError:
        groundedness, relevance = await _score_heuristic(question, answer, contexts)
    except Exception as exc:
        log.warning("trulens_scorer: scoring error: %s", exc)

    needs_review = (
        (groundedness is not None and groundedness < GROUNDEDNESS_THRESHOLD)
        or (relevance is not None and relevance < RELEVANCE_THRESHOLD)
    )

    if needs_review:
        log.info(
            "trulens_scorer: query %s flagged for review "
            "(groundedness=%.2f relevance=%.2f)",
            query_id,
            groundedness or 0.0,
            relevance or 0.0,
        )

    await _write_score(query_id, question, groundedness, relevance, needs_review)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_in_background(
    query_id: str,
    question: str,
    answer: str,
    contexts: list[str],
) -> None:
    """
    Fire-and-forget: schedule TruLens scoring as a background asyncio task.
    Call this from the query router after returning the HTTP response.
    """
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(
            _score_query(query_id, question, answer, contexts),
            name=f"trulens-score-{query_id}",
        )
    except RuntimeError:
        # No running loop (e.g., test context) — skip silently
        log.debug("trulens_scorer: no event loop, skipping background score")


async def get_review_queue(limit: int = 50) -> list[dict]:
    """Return flagged queries that need human review (newest first)."""
    try:
        import asyncpg  # noqa: PLC0415

        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/kgrag")
        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(
                """
                SELECT id, query_id, question, groundedness, answer_relevance, scored_at
                FROM trulens_scores
                WHERE needs_review = TRUE
                ORDER BY scored_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]
        finally:
            await conn.close()
    except Exception as exc:
        log.warning("trulens_scorer: get_review_queue failed: %s", exc)
        return []
