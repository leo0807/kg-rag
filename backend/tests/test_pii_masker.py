"""
Unit tests for src/services/pii_masker.py
Tests PIIMasker.mask() and mask_dict() with real regex patterns (no mocks needed).
"""
import pytest
from src.services.pii_masker import PIIMasker, pii_masker


# ── Basic behaviour ──────────────────────────────────────────────────────────

def test_mask_empty_string():
    assert pii_masker.mask("") == ""


def test_mask_none_returns_falsy():
    # mask(None) should return None (short-circuit on falsy)
    assert not pii_masker.mask(None)


def test_mask_no_pii_unchanged():
    text = "本文件描述了工艺流程的总体要求。"
    assert pii_masker.mask(text) == text


# ── Phone numbers ────────────────────────────────────────────────────────────

def test_mask_mobile_phone():
    result = pii_masker.mask("联系电话：13812345678")
    assert "13812345678" not in result
    assert "***" in result


def test_mask_landline_phone():
    result = pii_masker.mask("座机：0755-12345678")
    assert "12345678" not in result


# ── Email ────────────────────────────────────────────────────────────────────

def test_mask_email():
    result = pii_masker.mask("邮箱：engineer@example.com 请联系。")
    assert "engineer@example.com" not in result
    assert "@" not in result or "***@" in result


# ── ID card ─────────────────────────────────────────────────────────────────

def test_mask_id_card_18_digit():
    result = pii_masker.mask("身份证：110101199001011234")
    assert "110101199001011234" not in result


def test_mask_id_card_with_x():
    result = pii_masker.mask("ID: 11010119900101123X")
    assert "11010119900101123X" not in result


# ── Personnel names ──────────────────────────────────────────────────────────

def test_mask_author_name():
    result = pii_masker.mask("编制：张三丰")
    assert "张三丰" not in result
    assert "***" in result


def test_mask_reviewer_name():
    result = pii_masker.mask("审核：李四")
    assert "李四" not in result


def test_mask_approver_name():
    result = pii_masker.mask("批准：王五六七")
    assert "王五六七" not in result


# ── Multiple PII in one string ───────────────────────────────────────────────

def test_mask_multiple_pii():
    text = "编制：张三，手机：13900000001，邮箱：foo@bar.com"
    result = pii_masker.mask(text)
    assert "张三" not in result
    assert "13900000001" not in result
    assert "foo@bar.com" not in result


# ── mask_dict ────────────────────────────────────────────────────────────────

def test_mask_dict_targets_specified_fields():
    d = {"name": "编制：张三", "title": "工艺规范", "phone": "13812345678"}
    out = PIIMasker().mask_dict(d, fields=["name", "phone"])
    assert "张三" not in out["name"]
    assert "13812345678" not in out["phone"]
    assert out["title"] == "工艺规范"   # untouched


def test_mask_dict_does_not_modify_original():
    original = {"field": "编制：赵六"}
    out = PIIMasker().mask_dict(original, fields=["field"])
    assert original["field"] == "编制：赵六"
    assert out["field"] != original["field"]


def test_mask_dict_skips_missing_fields():
    d = {"a": "text"}
    out = PIIMasker().mask_dict(d, fields=["b"])  # "b" not in d
    assert out == {"a": "text"}


def test_mask_dict_skips_non_string_values():
    d = {"count": 42, "note": "编制：测试"}
    out = PIIMasker().mask_dict(d, fields=["count", "note"])
    assert out["count"] == 42          # integer untouched
    assert "测试" not in out["note"]


# ── Module-level singleton ───────────────────────────────────────────────────

def test_module_singleton_is_piimasker():
    assert isinstance(pii_masker, PIIMasker)
