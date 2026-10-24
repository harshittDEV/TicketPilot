"""
Tests for Central Recovery Policy and Retry Budgets (Phase 6).

Verifies:
- Configurable retry attempts and exponential backoff calculations.
- Enforcing maximum backoff caps and cumulative execution deadlines.
- Cancellation and non-recoverable error restrictions (zero retries).
- Human intervention pause transitions.
- Idempotency guardrails preventing repeated uncertain side effects.
- Zero-latency deterministic testing via ZeroSleeper.
"""

import pytest

from app.agent.recovery.errors import (
    ActionValidationError,
    AuthenticationFailureError,
    CaptchaChallengeError,
    HumanInterventionRequiredError,
    OperationTimeoutError,
    RateLimitError,
    SessionExpiredError,
    TransientNetworkError,
    UnknownOutcomeError,
)
from app.agent.recovery.policy import (
    RecoveryAction,
    RecoveryDecision,
    RecoveryPolicy,
    ZeroSleeper,
)


class TestRecoveryPolicyCalculations:
    """Verify deterministic backoff and limit evaluations."""

    def test_default_policy_settings(self):
        policy = RecoveryPolicy(
            max_attempts=3,
            initial_backoff_seconds=0.5,
            backoff_multiplier=2.0,
            max_backoff_seconds=5.0,
            max_cumulative_seconds=30.0,
        )
        assert policy.max_attempts == 3
        assert policy.calculate_backoff(1) == 0.5
        assert policy.calculate_backoff(2) == 1.0
        assert policy.calculate_backoff(3) == 2.0
        assert policy.calculate_backoff(4) == 4.0
        assert policy.calculate_backoff(5) == 5.0  # Capped at max_backoff_seconds

    def test_transient_error_retry_decision(self):
        policy = RecoveryPolicy(max_attempts=3, initial_backoff_seconds=0.5, backoff_multiplier=2.0)
        err = TransientNetworkError("Connection reset")

        # Attempt 1: retry with 0.5s backoff
        d1 = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0, is_idempotent=True)
        assert d1.action == RecoveryAction.RETRY
        assert d1.backoff_seconds == 0.5
        assert d1.attempt_number == 1

        # Attempt 2: retry with 1.0s backoff
        d2 = policy.evaluate(err, attempt=2, elapsed_retry_time=0.5, is_idempotent=True)
        assert d2.action == RecoveryAction.RETRY
        assert d2.backoff_seconds == 1.0

        # Attempt 3: reached max_attempts (3) -> FAIL_SAFELY
        d3 = policy.evaluate(err, attempt=3, elapsed_retry_time=1.5, is_idempotent=True)
        assert d3.action == RecoveryAction.FAIL_SAFELY
        assert "exhausted" in d3.reason.lower()

    def test_deadline_exhaustion_stops_retries(self):
        policy = RecoveryPolicy(max_attempts=5, max_cumulative_seconds=2.0)
        err = TransientNetworkError("Network blip")

        # Cumulative elapsed is already at or past deadline
        d = policy.evaluate(err, attempt=2, elapsed_retry_time=2.5, is_idempotent=True)
        assert d.action == RecoveryAction.FAIL_SAFELY
        assert "deadline" in d.reason.lower()

    def test_cancellation_aborts_immediately(self):
        policy = RecoveryPolicy(max_attempts=3)
        err = TransientNetworkError("Temporary drop")

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0, is_cancelled=True)
        assert d.action == RecoveryAction.FAIL_SAFELY
        assert "cancelled" in d.reason.lower()

    def test_validation_errors_never_retried(self):
        policy = RecoveryPolicy(max_attempts=5)
        err = ActionValidationError("Invalid station code: XYZ")

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0, is_idempotent=True)
        assert d.action == RecoveryAction.FAIL_SAFELY
        assert "validation" in d.reason.lower()

    def test_authentication_errors_never_retried(self):
        policy = RecoveryPolicy(max_attempts=5)
        err = AuthenticationFailureError("Invalid user credentials")

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0)
        assert d.action == RecoveryAction.FAIL_SAFELY
        assert "authentication" in d.reason.lower()

    def test_captcha_triggers_human_intervention_pause(self):
        policy = RecoveryPolicy(max_attempts=5)
        err = CaptchaChallengeError("IRCTC CAPTCHA challenge presented")

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0)
        assert d.action == RecoveryAction.PAUSE_FOR_HUMAN
        assert d.requires_human is True
        assert "captcha" in d.reason.lower()

    def test_session_expired_triggers_human_intervention_pause(self):
        policy = RecoveryPolicy(max_attempts=5)
        err = SessionExpiredError("Session timed out")

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0)
        assert d.action == RecoveryAction.PAUSE_FOR_HUMAN
        assert d.requires_human is True

    def test_non_idempotent_unknown_outcome_prohibits_blind_retry(self):
        policy = RecoveryPolicy(max_attempts=5)
        err = UnknownOutcomeError("Payment authorization timed out without confirmation")

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0, is_idempotent=False)
        assert d.action in (RecoveryAction.STOP_UNCERTAIN, RecoveryAction.PAUSE_FOR_HUMAN)
        assert d.requires_human is True
        assert "uncertain" in d.reason.lower()

    def test_rate_limit_honors_retry_after(self):
        policy = RecoveryPolicy(max_attempts=3, max_cumulative_seconds=60.0)
        err = RateLimitError("Rate limit exceeded", retry_after_seconds=5.0)

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0, is_idempotent=True)
        assert d.action == RecoveryAction.RETRY
        assert d.backoff_seconds == 5.0

    def test_rate_limit_retry_after_exceeding_deadline_fails_safely(self):
        policy = RecoveryPolicy(max_attempts=3, max_cumulative_seconds=10.0)
        # Server requests 30s wait, but our deadline is 10s
        err = RateLimitError("Rate limit exceeded", retry_after_seconds=30.0)

        d = policy.evaluate(err, attempt=1, elapsed_retry_time=0.0, is_idempotent=True)
        assert d.action == RecoveryAction.FAIL_SAFELY
        assert "exceeds" in d.reason.lower()

    @pytest.mark.asyncio
    async def test_zero_sleeper_executes_deterministically_instantly(self):
        sleeper = ZeroSleeper()
        # Mock 100 seconds of sleep executes in < 0.001s without blocking
        await sleeper.sleep(100.0)
        assert sleeper.total_slept == 100.0
        assert sleeper.call_count == 1
