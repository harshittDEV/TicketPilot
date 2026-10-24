"""
Comprehensive tests for deep secret redaction and privacy enforcement (Phase 7).
"""

from __future__ import annotations

import pytest

from app.integrations.security.redaction import (
    is_sensitive_key,
    redact_exception,
    redact_http_headers,
    redact_sensitive_data,
    redact_string,
)


class TestSecretRedactionDeep:
    """Tests proving secrets are deeply redacted from data structures, strings, headers, and exceptions."""

    def test_sensitive_key_detection(self):
        """Detects standard and case-variant sensitive key names."""
        assert is_sensitive_key("password")
        assert is_sensitive_key("PASSWORD")
        assert is_sensitive_key("user_password")
        assert is_sensitive_key("otp")
        assert is_sensitive_key("totpCode")
        assert is_sensitive_key("cvv")
        assert is_sensitive_key("cvc_number")
        assert is_sensitive_key("creditcard")
        assert is_sensitive_key("cardNumber")
        assert is_sensitive_key("api_key")
        assert is_sensitive_key("secretKey")
        assert is_sensitive_key("bearer_token")
        assert is_sensitive_key("auth_token")
        assert is_sensitive_key("sessionid")

        # Non-sensitive keys remain False
        assert not is_sensitive_key("train_number")
        assert not is_sensitive_key("destination_station")
        assert not is_sensitive_key("fare_amount")

    def test_nested_dictionary_and_list_redaction(self):
        """Redacts sensitive values at arbitrary nesting depths in dicts and lists."""
        payload = {
            "task_id": "task-100",
            "request": {
                "username": "agent_user",
                "password": "SuperSecretPassword123!",
                "credentials": {
                    "api_key": "sk-live-abcdef123456",
                    "pin": 1234,
                },
                "passengers": [
                    {
                        "passengerName": "Alice Smith",
                        "age": 30,
                        "id_proof": {"passport": "Z1234567"},
                    },
                    {
                        "passengerName": "Bob Jones",
                        "age": 32,
                        "dob": "1994-01-01",
                    },
                ],
            },
            "payment": {
                "upi_id": "user@okhdfcbank",
                "card_number": "4111222233334444",
                "cvv": "999",
            },
            "public_info": {
                "train_name": "Shatabdi Express",
                "travel_date": "2026-11-20",
            },
        }

        sanitized = redact_sensitive_data(payload)

        # Sensitive fields replaced with [REDACTED]
        assert sanitized["request"]["password"] == "[REDACTED]"
        assert sanitized["request"]["credentials"]["api_key"] == "[REDACTED]"
        assert sanitized["request"]["credentials"]["pin"] == "[REDACTED]"
        assert sanitized["request"]["passengers"][0]["passengerName"] == "[REDACTED]"
        assert sanitized["request"]["passengers"][0]["id_proof"]["passport"] == "[REDACTED]"
        assert sanitized["request"]["passengers"][1]["passengerName"] == "[REDACTED]"
        assert sanitized["request"]["passengers"][1]["dob"] == "[REDACTED]"
        assert sanitized["payment"]["card_number"] == "[REDACTED]"
        assert sanitized["payment"]["cvv"] == "[REDACTED]"

        # Non-sensitive values preserved exactly
        assert sanitized["task_id"] == "task-100"
        assert sanitized["request"]["username"] == "agent_user"
        assert sanitized["request"]["passengers"][0]["age"] == 30
        assert sanitized["public_info"]["train_name"] == "Shatabdi Express"
        assert sanitized["public_info"]["travel_date"] == "2026-11-20"

    def test_bearer_token_string_pattern_redaction(self):
        """Redacts Bearer tokens embedded in free-text strings."""
        raw_msg = "Request failed with header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
        sanitized = redact_string(raw_msg)
        assert "eyJhbGci" not in sanitized
        assert "Bearer [REDACTED]" in sanitized

    def test_credit_card_pattern_redaction(self):
        """Redacts 16-digit credit card sequences embedded in plain text."""
        raw_text = "Transaction declined for card 4111-2222-3333-4444 at gateway"
        sanitized = redact_string(raw_text)
        assert "4111-2222-3333-4444" not in sanitized
        assert "[REDACTED]" in sanitized

    def test_url_credentials_and_query_secrets_redaction(self):
        """Redacts username:password in URLs and secret query parameters."""
        raw_url = "https://user:mySecretPassword@proxy.irctc.internal:8080/query?token=secretToken123&travel_date=2026-11-20"
        sanitized = redact_string(raw_url)
        assert "mySecretPassword" not in sanitized
        assert "secretToken123" not in sanitized
        assert "user:[REDACTED]@" in sanitized
        assert "token=[REDACTED]" in sanitized
        assert "travel_date=2026-11-20" in sanitized

    def test_http_headers_redaction(self):
        """Redacts Authorization, Cookie, and API key headers."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer secret-jwt-token-999",
            "Cookie": "session_id=abc123xyz; secure_token=topsecret",
            "X-Api-Key": "live_key_999888",
            "User-Agent": "TatkalAgent/1.0",
        }
        sanitized = redact_http_headers(headers)
        assert sanitized["Content-Type"] == "application/json"
        assert sanitized["User-Agent"] == "TatkalAgent/1.0"
        assert sanitized["Authorization"] == "[REDACTED]"
        assert sanitized["Cookie"] == "[REDACTED]"
        assert sanitized["X-Api-Key"] == "[REDACTED]"

    def test_exception_redaction(self):
        """Sanitizes exception error messages containing passwords or tokens."""
        exc = RuntimeError("Authentication failed for https://admin:SuperSecretPass@auth.irctc.co.in/login?token=abc12345")
        sanitized_msg = redact_exception(exc)
        assert "SuperSecretPass" not in sanitized_msg
        assert "abc12345" not in sanitized_msg
        assert "admin:[REDACTED]@" in sanitized_msg
        assert "token=[REDACTED]" in sanitized_msg
