"""
Unit tests for src/services/simulation/parametric_search.py
Tests the pure Python helper methods (_build_filters, _rank, _apply_range_filter)
without a DB connection.
"""
import pytest
from src.services.simulation.parametric_search import (
    ParametricSearch,
    parametric_search,
    _DOMAIN_CHOICES,
    _CONF_CHOICES,
)


# ── Lightweight fake case object ──────────────────────────────────────────────

class _Case:
    def __init__(self, **kwargs):
        self.domain          = kwargs.get("domain", "structural")
        self.application     = kwargs.get("application", "")
        self.software        = kwargs.get("software", "")
        self.confidence_level = kwargs.get("confidence_level", "参考")
        self.project_code    = kwargs.get("project_code", "")
        self.inputs          = kwargs.get("inputs", {})
        self.description     = kwargs.get("description", "")
        self.id              = kwargs.get("id", 1)
        self.case_name       = kwargs.get("case_name", "test")
        self.case_code       = kwargs.get("case_code", "TC001")
        self.related_specs   = kwargs.get("related_specs", [])
        self.created_at      = None


# ── _rank ─────────────────────────────────────────────────────────────────────

def test_rank_verified_gets_bonus():
    s = ParametricSearch()
    verified = _Case(confidence_level="已验证", inputs={"material": "aluminum"})
    ref = _Case(confidence_level="参考", inputs={"material": "aluminum"})
    ranked = s._rank([ref, verified], {"material": "aluminum"})
    assert ranked[0].confidence_level == "已验证"


def test_rank_keyword_hit_increases_score():
    s = ParametricSearch()
    match = _Case(description="aluminum frame thermal simulation", confidence_level="参考")
    no_match = _Case(description="generic case", confidence_level="参考")
    ranked = s._rank([no_match, match], {"material": "aluminum", "load_type": "thermal"})
    assert ranked[0].description == match.description


def test_rank_empty_criteria_returns_all():
    s = ParametricSearch()
    cases = [_Case(id=i) for i in range(5)]
    result = s._rank(cases, {})
    assert len(result) == 5


def test_rank_preserves_list_length():
    s = ParametricSearch()
    cases = [_Case(id=i) for i in range(10)]
    result = s._rank(cases, {"material": "steel"})
    assert len(result) == 10


# ── _apply_range_filter ───────────────────────────────────────────────────────

def test_range_filter_no_filter_returns_all():
    s = ParametricSearch()
    cases = [_Case(inputs={"temperature": 100}), _Case(inputs={"temperature": 500})]
    result = s._apply_range_filter(cases, {})
    assert len(result) == 2


def test_range_filter_temperature_in_range():
    s = ParametricSearch()
    cases = [
        _Case(inputs={"temperature": 150}),
        _Case(inputs={"temperature": 600}),
    ]
    result = s._apply_range_filter(cases, {"temperature_range": [100, 300]})
    assert len(result) == 1
    assert result[0].inputs["temperature"] == 150


def test_range_filter_pressure_in_range():
    s = ParametricSearch()
    cases = [
        _Case(inputs={"pressure": 5.0}),
        _Case(inputs={"pressure": 50.0}),
    ]
    result = s._apply_range_filter(cases, {"pressure_range": [0.0, 10.0]})
    assert len(result) == 1
    assert result[0].inputs["pressure"] == 5.0


def test_range_filter_chinese_key():
    s = ParametricSearch()
    cases = [_Case(inputs={"温度": 200}), _Case(inputs={"温度": 800})]
    result = s._apply_range_filter(cases, {"temperature_range": [100, 300]})
    assert len(result) == 1


def test_range_filter_missing_key_passes_through():
    s = ParametricSearch()
    # Case has no temperature key — should pass through filter unchanged
    case = _Case(inputs={"pressure": 10.0})
    result = s._apply_range_filter([case], {"temperature_range": [50, 200]})
    assert len(result) == 1


def test_range_filter_non_numeric_passes_through():
    s = ParametricSearch()
    case = _Case(inputs={"temperature": "N/A"})
    result = s._apply_range_filter([case], {"temperature_range": [100, 200]})
    assert len(result) == 1   # non-numeric doesn't raise, passes through


# ── suggest_gaps pure data ───────────────────────────────────────────────────

def test_domain_choices_constants():
    assert "structural" in _DOMAIN_CHOICES
    assert "thermal" in _DOMAIN_CHOICES
    assert "fluid" in _DOMAIN_CHOICES


def test_conf_choices_constants():
    assert "已验证" in _CONF_CHOICES
    assert "参考" in _CONF_CHOICES


# ── module singleton ──────────────────────────────────────────────────────────

def test_module_singleton():
    assert isinstance(parametric_search, ParametricSearch)
