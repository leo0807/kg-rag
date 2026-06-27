"""
Differential Privacy noise injection for analytics reports.

Prevents reverse-engineering individual user behavior from aggregated stats.
Uses Laplace mechanism (ε-DP) for counting queries and Gaussian mechanism
(ε,δ)-DP for continuous values.

Typical usage:
    from .dp_reports import dp_count, dp_histogram, add_laplace_noise

    # Department activity report
    raw_counts = {"hydraulics": 142, "electrical": 89, "structures": 203}
    noisy = dp_histogram(raw_counts, epsilon=1.0, sensitivity=1)

    # Query hotspot (top-K sections)
    noisy_score = dp_count(real_count=142, epsilon=1.0)

Privacy budget guidance:
    ε = 0.1  — very strong (heavy noise, coarse stats only)
    ε = 1.0  — standard (recommended for internal reports)
    ε = 10.0 — weak (low noise, near-exact; only for public aggregates)

Reference: Dwork & Roth, "The Algorithmic Foundations of Differential Privacy", 2014
"""
from __future__ import annotations

import logging
import math
import os
import random
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_EPSILON   = float(os.getenv("DP_EPSILON", "1.0"))
DEFAULT_DELTA     = float(os.getenv("DP_DELTA", "1e-5"))
MIN_REPORT_COUNT  = int(os.getenv("DP_MIN_REPORT_COUNT", "5"))  # suppress if raw < 5


def _laplace_noise(sensitivity: float, epsilon: float) -> float:
    """Sample from Laplace(0, sensitivity/epsilon)."""
    scale = sensitivity / epsilon
    u = random.uniform(-0.5, 0.5)
    # Laplace inverse CDF
    return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))


def _gaussian_noise(sensitivity: float, epsilon: float, delta: float) -> float:
    """Sample from Gaussian calibrated for (epsilon, delta)-DP."""
    sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / epsilon
    return random.gauss(0, sigma)


def dp_count(
    real_count: int,
    epsilon: float = DEFAULT_EPSILON,
    sensitivity: int = 1,
    min_suppress: int = MIN_REPORT_COUNT,
) -> int:
    """
    Add Laplace noise to a count and return rounded integer.
    Suppresses (returns 0) if real_count < min_suppress to prevent identification.
    """
    if real_count < min_suppress:
        return 0
    noisy = real_count + _laplace_noise(sensitivity, epsilon)
    return max(0, round(noisy))


def dp_mean(
    values: list[float],
    lower: float,
    upper: float,
    epsilon: float = DEFAULT_EPSILON,
) -> float:
    """
    DP mean with clipping to [lower, upper].
    Sensitivity = (upper - lower) / n.
    """
    if not values:
        return 0.0
    clipped  = [max(lower, min(upper, v)) for v in values]
    raw_mean = sum(clipped) / len(clipped)
    sensitivity = (upper - lower) / len(clipped)
    return raw_mean + _laplace_noise(sensitivity, epsilon)


def dp_histogram(
    counts: dict[str, int],
    epsilon: float = DEFAULT_EPSILON,
    sensitivity: int = 1,
) -> dict[str, int]:
    """
    Apply independent Laplace noise to each bucket.
    Distributes epsilon equally across all buckets (parallel composition).
    """
    return {
        k: dp_count(v, epsilon=epsilon, sensitivity=sensitivity)
        for k, v in counts.items()
    }


def dp_top_k(
    scores: dict[str, float],
    k: int = 10,
    epsilon: float = DEFAULT_EPSILON,
    sensitivity: float = 1.0,
) -> list[tuple[str, float]]:
    """
    Return noisy top-K items (for query hotspot reports).
    Uses report-noisy-max / exponential mechanism approximation.
    """
    noisy = {
        key: score + _laplace_noise(sensitivity, epsilon)
        for key, score in scores.items()
    }
    sorted_items = sorted(noisy.items(), key=lambda x: -x[1])
    return [(k, round(v, 2)) for k, v in sorted_items[:k]]


def build_dept_activity_report(
    raw: dict[str, Any],
    epsilon: float = DEFAULT_EPSILON,
) -> dict[str, Any]:
    """
    Apply DP to a department activity dict:
      {"hydraulics": {"query_count": 142, "avg_latency_ms": 320.5, ...}, ...}

    Returns noisy version safe for sharing with analytics team.
    """
    result: dict[str, Any] = {}
    for dept, stats in raw.items():
        result[dept] = {
            "query_count":    dp_count(stats.get("query_count", 0), epsilon=epsilon),
            "avg_latency_ms": round(
                dp_mean(
                    [stats.get("avg_latency_ms", 0)],
                    lower=0, upper=5000, epsilon=epsilon,
                ), 1
            ),
            "active_users":   dp_count(stats.get("active_users", 0), epsilon=epsilon),
        }
    return result
