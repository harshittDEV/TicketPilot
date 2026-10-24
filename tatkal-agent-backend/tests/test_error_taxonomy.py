"""
Tests for Standardized Error Taxonomy and Classification (Phase 6).

Verifies:
- Structured error categories and metadata.
- Exception classification from errors/strings.
- Strict sensitive data redaction in error context.
- Distinguishing recoverable from non-recoverable and human-intervention errors.
"""

import pytest

from app.agent.recovery.errors import (
    ActionValidationError,
    AuthenticationFailureError,
    CaptchaChallengeError,
    ClassifiedRecoveryError,
    ErrorCategory,
    HumanInterventionRequiredError,
    OperationTimeoutError,
    RateLimitError,
    ServiceUnavailableRecoveryError,
    SessionExpiredError,
    TransientNetworkError,
    UnknownOutcomeError,
    classify_exception,
)


class TestErrorTaxonomyMetadata:
    """Verify metadata and structure across error taxonomy classes."""

    def test_transient_network_error_defaults(self):
        err = TransientNetworkError("Connection refused")
        assert err.category == ErrorCategory.TRANSIENT_NETWORK
        assert err.code == "TRANSIENT_NETWORK_ERROR"
        assert err.recoverable is True
        assert err.requires_human is False
        assert err.is_uncertain_outcome is False

    def test_operation_timeout_idempotent_vs_unknown(self):
        timeout_err = OperationTimeoutError("Deadline exceeded", is_uncertain_outcome=False)
        assert timeout_err.category == ErrorCategory.TIMEOUT
        assert timeout_err.recoverable is True
        assert timeout_err.is_uncertain_outcome is False

        uncertain_err = UnknownOutcomeError("Submission timed out without ack")
        assert uncertain_err.category == ErrorCategory.UNKNOWN_OUTCOME
        assert uncertain_err.recoverable is False
        assert uncertain_err.requires_human is True
        assert uncertain_err.is_uncertain_outcome is True

    def test_captcha_challenge_requires_human(self):
        err = CaptchaChallengeError("Cloudflare Turnstile challenge detected")
        assert err.category == ErrorCategory.CAPTCHA_CHALLENGE
        assert err.recoverable is False
        assert err.requires_human is True
        assert err.is_uncertain_outcome is False
        assert "human" in err.retry_guidance.lower()

    def test_session_expired_requires_human(self):
        err = SessionExpiredError("Session cookie invalid or expired")
        assert err.category == ErrorCategory.SESSION_EXPIRED
        assert err.recoverable is False
        assert err.requires_human is True

    def test_validation_error_not_recoverable(self):
        err = ActionValidationError("Parameter 'amount' must be positive")
        assert err.category == ErrorCategory.VALIDATION_ERROR
        assert err.recoverable is False
        assert err.requires_human is False

    def test_authentication_error_not_recoverable(self):
        err = AuthenticationFailureError("Bad username or password")
        assert err.category == ErrorCategory.AUTHENTICATION_ERROR
        assert err.recoverable is False
        assert err.requires_human is False

    def test_rate_limit_error_with_retry_after(self):
        err = RateLimitError("Rate limit exceeded", retry_after_seconds=30.0)
        assert err.category == ErrorCategory.RATE_LIMIT
        assert err.recoverable is True
        assert err.retry_after_seconds == 30.0

    def test_sensitive_data_redacted_in_safe_context(self):
        raw_ctx = {
            "username": "agent_user",
            "password": "SUPER_SECRET_PASSWORD_123",
            "otp": "987654",
            "session_token": "token_abc123xyz",
            "card_number": "4111222233334444",
            "non_sensitive_id": "req-999",
        }
        err = ClassifiedRecoveryError(
            message="Test error",
            category=ErrorCategory.AUTHENTICATION_ERROR,
            code="AUTH_FAIL",
            safe_context=raw_ctx,
        )
        as_dict = err.to_dict()
        ctx = as_dict["context"]

        assert ctx["non_sensitive_id"] == "req-999"
        assert ctx["username"] == "agent_user"
        assert ctx["password"] == "[REDACTED]"
        assert ctx["otp"] == "[REDACTED]"
        assert ctx["session_token"] == "[REDACTED]"
        assert ctx["card_number"] == "[REDACTED]"
        # Raw secrets must never appear anywhere in the string or dict
        assert "SUPER_SECRET_PASSWORD_123" not in str(as_dict)
        assert "987654" not in str(as_dict)


class TestClassifyException:
    """Verify classify_exception logic across diverse inputs."""

    def test_classify_transient_network_idempotent(self):
        exc = ConnectionResetError("Connection reset by peer")
        classified = classify_exception(exc, action_type="inspect", is_idempotent=True)
        assert isinstance(classified, TransientNetworkError)
        assert classified.recoverable is True

    def test_classify_network_drop_on_non_idempotent_becomes_unknown_outcome(self):
        exc = ConnectionResetError("Connection reset by peer")
        classified = classify_exception(exc, action_type="submit_payment", is_idempotent=False)
        assert isinstance(classified, UnknownOutcomeError)
        assert classified.is_uncertain_outcome is True
        assert classified.requires_human is True

    def test_classify_timeout_idempotent_vs_non_idempotent(self):
        import asyncio
        exc = asyncio.TimeoutError()

        # Idempotent action timeout is recoverable
        idemp = classify_exception(exc, action_type="get_page", is_idempotent=True)
        assert isinstance(idemp, OperationTimeoutError)
        assert idemp.recoverable is True

        # Non-idempotent action timeout has unknown outcome
        non_idemp = classify_exception(exc, action_type="confirm_booking", is_idempotent=False)
        assert isinstance(non_idemp, UnknownOutcomeError)
        assert non_idemp.is_uncertain_outcome is True
        assert non_idemp.requires_human is True

    def test_classify_captcha_challenge(self):
        exc = RuntimeError("IRCTC returned CAPTCHA image challenge required to proceed")
        classified = classify_exception(exc, action_type="submit_login")
        assert isinstance(classified, CaptchaChallengeError)
        assert classified.requires_human is True

    def test_classify_session_expired(self):
        exc = RuntimeError("401 Unauthorized: Session timed out or expired")
        classified = classify_exception(exc, action_type="query_availability")
        assert isinstance(classified, SessionExpiredError)
        assert classified.requires_human is True

    def test_classify_rate_limit_with_retry_after(self):
        exc = RuntimeError("429 Too Many Requests: Rate limit exceeded. Retry-After: 45")
        classified = classify_exception(exc, action_type="find_trains")
        assert isinstance(classified, RateLimitError)
        assert classified.recoverable is True
        assert classified.retry_after_seconds == 45.0

    def test_classify_validation_error(self):
        exc = ValueError("Invalid passenger count: must be between 1 and 6")
        classified = classify_exception(exc, action_type="validate_plan")
        assert isinstance(classified, ActionValidationError)
        assert classified.recoverable is False

    def test_classify_fallback_unclassified(self):
        exc = Exception("Something bizarre and unexpected occurred")
        classified = classify_exception(exc, action_type="calculate", is_idempotent=True)
        assert classified.category == ErrorCategory.UNCLASSIFIED
        assert classified.recoverable is False
