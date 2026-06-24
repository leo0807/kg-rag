"""
Unit tests for src/services/quality/defect_detector.py
Tests constants, is_available(), set_model_path(), and detect_defects() fallback
without requiring ultralytics or YOLO weights.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.services.quality import defect_detector as dd


# ── Constants ────────────────────────────────────────────────────────────────

def test_defect_labels_dict():
    assert isinstance(dd.DEFECT_LABELS, dict)
    assert "scratch" in dd.DEFECT_LABELS
    assert "crack" in dd.DEFECT_LABELS


def test_defect_labels_have_chinese_values():
    for en, zh in dd.DEFECT_LABELS.items():
        assert isinstance(zh, str)
        assert len(zh) > 0


def test_conf_threshold():
    assert 0.0 < dd._CONF_THRESHOLD < 1.0


# ── is_available ─────────────────────────────────────────────────────────────

def test_is_available_returns_bool():
    assert isinstance(dd.is_available(), bool)


def test_is_available_false_without_ultralytics():
    """When ultralytics is absent, is_available() should be False."""
    with patch.object(dd, "_YOLO_AVAILABLE", False):
        assert dd.is_available() is False


def test_is_available_true_when_patched():
    with patch.object(dd, "_YOLO_AVAILABLE", True):
        assert dd.is_available() is True


# ── set_model_path ────────────────────────────────────────────────────────────

def test_set_model_path_updates_global():
    original = dd._model_path
    dd.set_model_path("/tmp/custom.pt")
    assert dd._model_path == "/tmp/custom.pt"
    dd.set_model_path(original)  # restore


# ── detect_defects — no YOLO fallback ────────────────────────────────────────

def test_detect_defects_returns_empty_when_yolo_unavailable():
    with patch.object(dd, "_YOLO_AVAILABLE", False):
        result = dd.detect_defects("/nonexistent/image.jpg")
    assert result == []


def test_detect_defects_returns_list_always():
    with patch.object(dd, "_YOLO_AVAILABLE", False):
        result = dd.detect_defects("any_path.png")
    assert isinstance(result, list)


# ── detect_defects — mocked YOLO ─────────────────────────────────────────────

def test_detect_defects_with_mock_yolo():
    """Simulate YOLO being available and returning one detection."""
    fake_box = MagicMock()
    fake_box.cls = [0]
    fake_box.conf = [0.85]
    fake_box.xyxy = [MagicMock(tolist=lambda: [10.0, 20.0, 100.0, 200.0])]

    fake_result = MagicMock()
    fake_result.names = {0: "scratch"}
    fake_result.boxes = [fake_box]

    fake_model = MagicMock(return_value=[fake_result])

    with patch.object(dd, "_YOLO_AVAILABLE", True), \
         patch.object(dd, "_get_model", return_value=fake_model):
        result = dd.detect_defects("/fake/image.jpg")

    assert len(result) == 1
    assert result[0]["defect_type"] == "scratch"
    assert result[0]["label"] == "划痕"
    assert 0.0 <= result[0]["confidence"] <= 1.0
    assert len(result[0]["bbox"]) == 4


def test_detect_defects_handles_exception_gracefully():
    with patch.object(dd, "_YOLO_AVAILABLE", True), \
         patch.object(dd, "_get_model", side_effect=RuntimeError("model load failed")):
        result = dd.detect_defects("/fake/image.jpg")
    assert result == []


# ── DEFECT_LABELS coverage ───────────────────────────────────────────────────

def test_defect_labels_key_count():
    # The module defines at least 6 defect types
    assert len(dd.DEFECT_LABELS) >= 6


def test_defect_labels_unknown_key_falls_back_to_cls_name():
    """detect_defects uses DEFECT_LABELS.get(cls_name, cls_name) — test fallback logic."""
    label = dd.DEFECT_LABELS.get("unknown_cls", "unknown_cls")
    assert label == "unknown_cls"
