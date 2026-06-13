from datetime import datetime, timedelta
from jose import jwt, JWTError
from ..core.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: str, is_admin: bool, tenant_id: str | None = None) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload: dict = {
        "sub":      user_id,
        "is_admin": is_admin,
        "exp":      expire,
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("无效的 token")