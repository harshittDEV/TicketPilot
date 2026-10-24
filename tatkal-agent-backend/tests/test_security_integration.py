"""
Tests for Security and Credential Vault integration (Member 4).
"""

import pytest

from app.integrations.contracts import SecurityCheckRequest
from app.integrations.security.adapter import SecurityAdapter
from app.integrations.security.redaction import redact_sensitive_data
from app.integrations.security.vault import SecureCredentialStore


class TestDataRedaction:
    """Verify data redaction rules adapted from Member 4's security.test.js."""

    def test_redacts_passwords_and_passenger_names(self):
        input_data = {
            "action": "login",
            "password": "secret123",
            "passengerName": "Test User",
        }
        res = redact_sensitive_data(input_data)
        assert res["action"] == "login"
        assert res["password"] == "[REDACTED]"
        assert res["passengerName"] == "[REDACTED]"

    def test_redacts_sensitive_fields_in_nested_objects(self):
        input_data = {
            "event": "booking",
            "details": {
                "otp": "123456",
                "trainNumber": "12001",
            },
        }
        res = redact_sensitive_data(input_data)
        assert res["details"]["otp"] == "[REDACTED]"
        assert res["details"]["trainNumber"] == "12001"

    def test_does_not_modify_original_object(self):
        input_data = {"password": "secret123"}
        res = redact_sensitive_data(input_data)
        assert input_data["password"] == "secret123"
        assert res["password"] == "[REDACTED]"

    def test_redacts_common_sensitive_field_names(self):
        input_data = {
            "phone": "9999999999",
            "email": "test@example.com",
            "token": "secret-token",
            "cookie": "session-cookie",
            "paymentDetails": {
                "cardNumber": "4111111111111111",
                "cvv": "123",
            },
            "trainNumber": "12001",
        }
        res = redact_sensitive_data(input_data)
        assert res["phone"] == "[REDACTED]"
        assert res["email"] == "[REDACTED]"
        assert res["token"] == "[REDACTED]"
        assert res["cookie"] == "[REDACTED]"
        assert res["paymentDetails"]["cardNumber"] == "[REDACTED]"
        assert res["paymentDetails"]["cvv"] == "[REDACTED]"
        assert res["trainNumber"] == "12001"


class TestSecureCredentialStore:
    """Verify vault isolation and opaque token generation."""

    def test_store_and_retrieve_secret(self):
        vault = SecureCredentialStore()
        token = vault.store_secret(
            owner_id="user_42",
            secret_type="irctc_credentials",
            payload={"username": "irctc_user", "password": "SuperSecretPassword123"},
        )
        assert token.startswith("sec_ref_")
        assert "SuperSecretPassword123" not in token

        retrieved = vault.retrieve_secret(token, actor="orchestrator")
        assert retrieved is not None
        assert retrieved["password"] == "SuperSecretPassword123"

    def test_vault_repr_does_not_leak_secrets(self):
        vault = SecureCredentialStore()
        vault.store_secret(
            owner_id="user_1",
            secret_type="token",
            payload={"token": "top_secret_token"},
        )
        assert "top_secret_token" not in str(vault)
        assert "top_secret_token" not in repr(vault)
        assert "secrets_count=1" in repr(vault)

    def test_revoke_secret(self):
        vault = SecureCredentialStore()
        token = vault.store_secret(owner_id="u1", secret_type="auth", payload={"k": "v"})
        assert vault.has_secret(token) is True
        assert vault.revoke_secret(token) is True
        assert vault.has_secret(token) is False
        assert vault.retrieve_secret(token, "actor") is None


class TestSecurityAdapter:
    """Verify authorization checks and policy barriers."""

    @pytest.mark.asyncio
    async def test_prohibited_actions_blocked(self):
        adapter = SecurityAdapter()
        for bad_action in ("captcha_bypass", "anti_bot_circumvention", "auto_approve_payment"):
            req = SecurityCheckRequest(action=bad_action, actor="agent")
            res = await adapter.check_authorization(req)
            assert res.allowed is False
            assert "strictly prohibited" in res.reason

    @pytest.mark.asyncio
    async def test_payment_approval_requires_human(self):
        adapter = SecurityAdapter()

        # Automated agent cannot approve payment
        req_agent = SecurityCheckRequest(action="payment_approval", actor="agent_orchestrator")
        res_agent = await adapter.check_authorization(req_agent)
        assert res_agent.allowed is False
        assert "requires explicit human" in res_agent.reason

        # Human actor is allowed
        req_human = SecurityCheckRequest(action="payment_approval", actor="human")
        res_human = await adapter.check_authorization(req_human)
        assert res_human.allowed is True

    @pytest.mark.asyncio
    async def test_safe_action_allowed(self):
        adapter = SecurityAdapter()
        req = SecurityCheckRequest(action="read_train_schedule", actor="agent")
        res = await adapter.check_authorization(req)
        assert res.allowed is True

    @pytest.mark.asyncio
    async def test_health_check_and_metadata(self):
        adapter = SecurityAdapter()
        assert await adapter.health_check() is True
        meta = adapter.get_metadata()
        assert meta["name"] == "security"
        assert "captcha_bypass" in meta["prohibited_actions"]
