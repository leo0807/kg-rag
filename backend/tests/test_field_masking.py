"""Unit tests for field-level data masking."""
from src.services.auth.field_masking import mask_record, mask_records


def _admin():
    return ["admin"]


def _superadmin():
    return ["super_admin"]


def _viewer():
    return ["viewer"]


class TestPrivilegedRoles:
    def test_admin_sees_unmasked_record(self):
        record = {"email": "alice@example.com", "password_hash": "hash123"}
        result = mask_record("user", record, _admin())
        assert result["email"] == "alice@example.com"
        assert result["password_hash"] == "hash123"

    def test_super_admin_sees_unmasked_record(self):
        record = {"email": "alice@example.com", "phone": "13800138000"}
        result = mask_record("user", record, _superadmin())
        assert result["email"] == "alice@example.com"


class TestUserResourceMasking:
    def test_masks_email_middle(self):
        record = {"email": "alice@example.com"}
        result = mask_record("user", record, _viewer())
        assert result["email"] != "alice@example.com"
        assert "@" in result["email"]
        assert "***" in result["email"]

    def test_masks_password_hash_completely(self):
        record = {"password_hash": "bcrypt_hash_value"}
        result = mask_record("user", record, _viewer())
        assert result["password_hash"] == "***"

    def test_masks_phone_completely(self):
        record = {"phone": "13800138000"}
        result = mask_record("user", record, _viewer())
        assert result["phone"] == "***"

    def test_non_sensitive_fields_passed_through(self):
        record = {"username": "alice", "email": "a@b.com", "active": True}
        result = mask_record("user", record, _viewer())
        assert result["username"] == "alice"
        assert result["active"] is True

    def test_missing_sensitive_field_not_added(self):
        record = {"username": "alice"}
        result = mask_record("user", record, _viewer())
        assert "email" not in result


class TestAuditResourceMasking:
    def test_masks_ip_to_prefix_only(self):
        record = {"ip_address": "192.168.1.100", "action": "login"}
        result = mask_record("audit", record, _viewer())
        assert "192.168" in result["ip_address"]
        assert "1.100" not in result["ip_address"]

    def test_masks_user_agent(self):
        record = {"user_agent": "Mozilla/5.0 (Windows...)"}
        result = mask_record("audit", record, _viewer())
        assert result["user_agent"] == "Mozi***"

    def test_passes_through_non_sensitive_audit_fields(self):
        record = {"action": "read", "resource": "document"}
        result = mask_record("audit", record, _viewer())
        assert result["action"] == "read"


class TestUnknownResource:
    def test_unknown_resource_no_masking(self):
        record = {"data": "secret_looking_value", "meta": "info"}
        result = mask_record("widget", record, _viewer())
        assert result == record


class TestMaskRecords:
    def test_masks_list_of_records(self):
        # email regex needs ≥2 chars before @; use realistic addresses
        records = [
            {"email": "alice@example.com", "username": "a"},
            {"email": "bobby@example.com", "username": "b"},
        ]
        results = mask_records("user", records, _viewer())
        assert len(results) == 2
        for r in results:
            assert "***" in r["email"]

    def test_admin_list_unchanged(self):
        records = [{"email": "a@example.com"}]
        results = mask_records("user", records, _admin())
        assert results[0]["email"] == "a@example.com"

    def test_does_not_mutate_original_records(self):
        original = {"email": "a@example.com", "username": "a"}
        mask_record("user", original, _viewer())
        assert original["email"] == "a@example.com"
