"""K6.2: Design of Experiments (DOE) sampling — full factorial, LHS, Sobol, adaptive."""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Tuple


class DOESampler:
    """Generate parameter sample sets for parametric sweep studies."""

    # ── Full factorial ─────────────────────────────────────────────────────────
    def full_factorial(self, params: Dict[str, List]) -> List[Dict[str, Any]]:
        """Cartesian product of all discrete parameter levels."""
        keys = list(params.keys())
        levels = [params[k] for k in keys]

        def _product(pools: List[List]) -> List[Tuple]:
            result = [()]
            for pool in pools:
                result = [x + (y,) for x in result for y in pool]
            return result

        return [{keys[i]: combo[i] for i in range(len(keys))} for combo in _product(levels)]

    # ── Latin Hypercube Sampling ───────────────────────────────────────────────
    def latin_hypercube(
        self,
        params: Dict[str, Tuple[float, float]],
        n_samples: int,
    ) -> List[Dict[str, Any]]:
        """
        Stratified random sampling (LHS).
        params: {name: (min, max)}
        """
        keys = list(params.keys())
        n = n_samples
        samples: Dict[str, List[float]] = {k: [] for k in keys}

        for k in keys:
            lo, hi = params[k]
            # Create n strata, pick random point in each, shuffle
            strata = [(lo + (hi - lo) * (i + random.random()) / n) for i in range(n)]
            random.shuffle(strata)
            samples[k] = strata

        return [{k: samples[k][i] for k in keys} for i in range(n)]

    # ── Sobol sequence (simple scrambled, no external lib) ────────────────────
    def sobol(
        self,
        params: Dict[str, Tuple[float, float]],
        n_samples: int,
    ) -> List[Dict[str, Any]]:
        """
        Simplified Sobol-like low-discrepancy sequence.
        For production use, install `scipy` or `SALib`.
        """
        keys  = list(params.keys())
        d     = len(keys)
        result = []
        for i in range(1, n_samples + 1):
            point = {}
            for j, k in enumerate(keys):
                lo, hi = params[k]
                # Van der Corput sequence for dimension j+1
                base = j + 2  # 2, 3, 5, 7, ...
                n, frac = i, 0.0
                b = 1.0
                while n > 0:
                    b /= base
                    frac += (n % base) * b
                    n //= base
                point[k] = lo + frac * (hi - lo)
            result.append(point)
        return result

    # ── Adaptive sampling ─────────────────────────────────────────────────────
    def adaptive(
        self,
        params: Dict[str, Tuple[float, float]],
        existing_results: List[Dict[str, Any]],
        n_new: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Suggest new sample points in regions sparse in existing_results.
        Falls back to LHS if not enough results to analyse.
        """
        if len(existing_results) < 4:
            return self.latin_hypercube(params, n_new)

        keys = list(params.keys())
        # Find the midpoint of the largest gap in each dimension
        new_points: List[Dict[str, Any]] = []
        for _ in range(n_new):
            point = {}
            for k in keys:
                lo, hi = params[k]
                known = sorted(r.get(k, lo) for r in existing_results if k in r)
                if len(known) < 2:
                    point[k] = (lo + hi) / 2
                    continue
                # Find largest gap
                best_gap, best_mid = 0.0, (lo + hi) / 2
                prev = lo
                for v in known + [hi]:
                    gap = v - prev
                    if gap > best_gap:
                        best_gap = gap
                        best_mid = prev + gap / 2
                    prev = v
                # Add small jitter
                jitter = best_gap * 0.05 * (random.random() - 0.5)
                point[k] = max(lo, min(hi, best_mid + jitter))
            new_points.append(point)
        return new_points

    def generate(
        self,
        doe_type: str,
        params: Dict[str, Any],
        n_samples: int = 10,
        existing_results: List[Dict] | None = None,
    ) -> List[Dict[str, Any]]:
        """Dispatch to the appropriate sampling strategy."""
        if doe_type == "full_factorial":
            return self.full_factorial(params)
        if doe_type == "sobol":
            return self.sobol(params, n_samples)
        if doe_type == "adaptive":
            return self.adaptive(params, existing_results or [], n_samples)
        # default: latin_hypercube
        return self.latin_hypercube(params, n_samples)


doe_sampler = DOESampler()
