"""F2.4 — Field-level masking for sensitive data based on user role."""
from __future__ import annotations

import re

# Fields masked per resource for non-privileged roles
_MASKED_FIELDS: dict[str, list[str]] = {
    "user": ["password_hash", "email", "phone"],
    "document": ["author_email", "internal_notes"],
    "audit": ["ip_address", "user_agent"],
}

# Roles that see unmasked data
_PRIVILEGED_ROLES = {"super_admin", "admin"}

_EMAIL_RE = re.compile(r"(?<=\w{2})[\w.]+(?=@)")
_IP_RE    = re.compile(r"(\d+\.\d+)\.\d+\.\d+")


def _mask_value(field: str, value: object) -> object:
    if value is None:
        return None
    s = str(value)
    if field == "email":
        return _EMAIL_RE.sub("***", s)
    if field == "ip_address":
        return _IP_RE.sub(r"\1.*.*", s)
    if field in ("password_hash", "phone"):
        return "***"
    # generic: show first 4 chars
    return s[:4] + "***" if len(s) > 4 else "***"


def mask_record(resource: str, record: dict, user_roles: list[str]) -> dict:
    """Return a copy of record with sensitive fields masked for non-privileged users."""
    if any(r in _PRIVILEGED_ROLES for r in user_roles):
        return record
    fields_to_mask = _MASKED_FIELDS.get(resource, [])
    if not fields_to_mask:
        return record
    result = dict(record)
    for field in fields_to_mask:
        if field in result:
            result[field] = _mask_value(field, result[field])
    return result


def mask_records(resource: str, records: list[dict], user_roles: list[str]) -> list[dict]:
    return [mask_record(resource, r, user_roles) for r in records]
