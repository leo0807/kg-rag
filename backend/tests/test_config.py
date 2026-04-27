import pytest
from pydantic import ValidationError

from src.core.config import Settings


def test_default_jwt_secret_allowed_in_development():
    settings = Settings()

    assert settings.DEBUG is True
    assert settings.APP_ENV == "development"


def test_default_jwt_secret_rejected_in_production():
    with pytest.raises(ValidationError) as exc_info:
        Settings(DEBUG=False, APP_ENV="production")

    assert "JWT_SECRET" in str(exc_info.value)
