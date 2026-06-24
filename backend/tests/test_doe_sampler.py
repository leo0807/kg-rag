"""
Unit tests for src/services/simulation/doe_sampler.py
Pure math — no DB, no external services.
"""
import pytest
from src.services.simulation.doe_sampler import DOESampler, doe_sampler


# ── full_factorial ────────────────────────────────────────────────────────────

def test_full_factorial_single_param():
    s = DOESampler()
    result = s.full_factorial({"temp": [100, 200, 300]})
    assert len(result) == 3
    assert all("temp" in r for r in result)


def test_full_factorial_two_params():
    s = DOESampler()
    result = s.full_factorial({"a": [1, 2], "b": ["x", "y"]})
    assert len(result) == 4
    combos = {(r["a"], r["b"]) for r in result}
    assert (1, "x") in combos
    assert (2, "y") in combos


def test_full_factorial_empty_params():
    s = DOESampler()
    result = s.full_factorial({})
    # Empty product is a list with one empty dict
    assert result == [{}]


def test_full_factorial_three_params():
    s = DOESampler()
    result = s.full_factorial({"x": [0, 1], "y": [0, 1], "z": [0, 1]})
    assert len(result) == 8


# ── latin_hypercube ───────────────────────────────────────────────────────────

def test_lhs_count():
    s = DOESampler()
    result = s.latin_hypercube({"x": (0.0, 1.0), "y": (10.0, 20.0)}, n_samples=8)
    assert len(result) == 8


def test_lhs_values_in_range():
    s = DOESampler()
    result = s.latin_hypercube({"x": (0.0, 1.0)}, n_samples=20)
    for r in result:
        assert 0.0 <= r["x"] <= 1.0


def test_lhs_all_keys_present():
    s = DOESampler()
    result = s.latin_hypercube({"a": (1.0, 5.0), "b": (100.0, 200.0)}, n_samples=5)
    for r in result:
        assert "a" in r and "b" in r


# ── sobol ─────────────────────────────────────────────────────────────────────

def test_sobol_count():
    s = DOESampler()
    result = s.sobol({"x": (0.0, 1.0)}, n_samples=10)
    assert len(result) == 10


def test_sobol_values_in_range():
    s = DOESampler()
    result = s.sobol({"x": (5.0, 10.0), "y": (0.0, 100.0)}, n_samples=15)
    for r in result:
        assert 5.0 <= r["x"] <= 10.0
        assert 0.0 <= r["y"] <= 100.0


def test_sobol_deterministic():
    s = DOESampler()
    r1 = s.sobol({"p": (0.0, 1.0)}, n_samples=5)
    r2 = s.sobol({"p": (0.0, 1.0)}, n_samples=5)
    for a, b in zip(r1, r2):
        assert a == b


# ── adaptive ──────────────────────────────────────────────────────────────────

def test_adaptive_falls_back_to_lhs_when_few_results():
    s = DOESampler()
    result = s.adaptive({"x": (0.0, 1.0)}, existing_results=[], n_new=5)
    assert len(result) == 5


def test_adaptive_fills_gaps():
    s = DOESampler()
    existing = [{"x": 0.1}, {"x": 0.2}, {"x": 0.9}, {"x": 1.0}]
    result = s.adaptive({"x": (0.0, 1.0)}, existing_results=existing, n_new=3)
    assert len(result) == 3
    for r in result:
        assert 0.0 <= r["x"] <= 1.0


def test_adaptive_values_in_bounds():
    s = DOESampler()
    existing = [{"x": v} for v in [0.1, 0.3, 0.5, 0.7, 0.9]]
    result = s.adaptive({"x": (0.0, 1.0)}, existing_results=existing, n_new=4)
    for r in result:
        assert 0.0 <= r["x"] <= 1.0


# ── generate dispatch ─────────────────────────────────────────────────────────

def test_generate_full_factorial():
    s = DOESampler()
    result = s.generate("full_factorial", {"a": [1, 2], "b": [3, 4]})
    assert len(result) == 4


def test_generate_sobol():
    s = DOESampler()
    result = s.generate("sobol", {"x": (0.0, 1.0)}, n_samples=6)
    assert len(result) == 6


def test_generate_adaptive():
    s = DOESampler()
    result = s.generate("adaptive", {"x": (0.0, 1.0)}, n_samples=3, existing_results=[])
    assert len(result) == 3


def test_generate_defaults_to_lhs():
    s = DOESampler()
    result = s.generate("unknown_type", {"x": (0.0, 1.0)}, n_samples=5)
    assert len(result) == 5


# ── module singleton ──────────────────────────────────────────────────────────

def test_module_singleton():
    assert isinstance(doe_sampler, DOESampler)
