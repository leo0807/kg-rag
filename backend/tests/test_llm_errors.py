import pytest
from src.services.ai.errors import classify_llm_error, parse_response_for_business_error, LLMError


def test_403_with_model_disabled():
    err = classify_llm_error(
        status=403,
        response_text='{"code": 30003, "message": "Model disabled."}',
        model="some-disabled-model",
    )
    assert err.code == "model_unavailable"


def test_403_with_quota_keyword():
    err = classify_llm_error(
        status=403,
        response_text='{"error": "quota exceeded"}',
        model="",
    )
    assert err.code == "quota_exceeded"


def test_403_unknown_forbidden():
    err = classify_llm_error(
        status=403,
        response_text='{"error": "unknown"}',
        model="",
    )
    assert err.code == "forbidden"


def test_429_rate_limited():
    err = classify_llm_error(status=429, response_text="", model="")
    assert err.code == "rate_limited"


def test_401_auth_failed():
    err = classify_llm_error(status=401, response_text="", model="")
    assert err.code == "auth_failed"


def test_200_with_business_error_code():
    response_data = {"code": 20015, "message": "The parameter is invalid."}
    err = parse_response_for_business_error(response_data)
    assert err is not None
    assert err.code == "api_invalid_request"
    assert err.provider_code == 20015


def test_200_normal_choices_not_flagged():
    response_data = {"choices": [{"message": {"content": "ok"}}]}
    err = parse_response_for_business_error(response_data)
    assert err is None


def test_200_code_zero_not_flagged():
    err = parse_response_for_business_error({"code": 0, "message": "ok"})
    assert err is None


def test_403_model_not_found():
    err = classify_llm_error(403, '{"message": "model not found"}', model="bad-model")
    assert err.code == "model_unavailable"


def test_403_balance_keyword():
    err = classify_llm_error(403, '{"message": "insufficient balance"}', model="")
    assert err.code == "quota_exceeded"


def test_408_timeout():
    err = classify_llm_error(408, "", "")
    assert err.code == "timeout"


def test_504_timeout():
    err = classify_llm_error(504, "", "")
    assert err.code == "timeout"


def test_500_unknown():
    err = classify_llm_error(500, "", "")
    assert err.code == "unknown_error"
