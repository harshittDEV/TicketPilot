"""
Tests for Circuit Breaker Pattern (Phase 6).

Verifies:
- State transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.
- Fast-failing in OPEN state with CircuitBreakerOpenError.
- Probe limit enforcement in HALF_OPEN state.
- Validation / non-transient errors do NOT trip the breaker.
- Thread-safe concurrency behavior.
- Registry singleton management and metrics reporting.
"""

import threading
import time
import pytest

from app.agent.recovery.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
)
from app.agent.recovery.errors import ActionValidationError, CaptchaChallengeError


class TestCircuitBreakerLifecycle:
    """Verify state transitions and thresholds."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test_service", failure_threshold=3, cooldown_seconds=1.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True
        assert cb.failure_count == 0

    def test_closed_trips_to_open_after_threshold(self):
        cb = CircuitBreaker("test_service", failure_threshold=3, cooldown_seconds=1.0)
        
        cb.record_failure(RuntimeError("Failure 1"))
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1

        cb.record_failure(RuntimeError("Failure 2"))
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2

        cb.record_failure(RuntimeError("Failure 3"))
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_open_state_rejects_requests(self):
        cb = CircuitBreaker("test_service", failure_threshold=2, cooldown_seconds=10.0)
        cb.record_failure(RuntimeError("Err 1"))
        cb.record_failure(RuntimeError("Err 2"))
        assert cb.state == CircuitState.OPEN

        # Should not allow request while in cooldown
        assert cb.allow_request() is False
        assert cb.cooldown_remaining > 0

    def test_cooldown_transitions_to_half_open(self):
        # Short cooldown for test
        cb = CircuitBreaker("test_service", failure_threshold=2, cooldown_seconds=0.05, half_open_probes=2)
        cb.record_failure(RuntimeError("Err 1"))
        cb.record_failure(RuntimeError("Err 2"))
        assert cb.state == CircuitState.OPEN

        # Wait past cooldown
        time.sleep(0.06)

        # First request should be allowed and move to HALF_OPEN
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

        # Second probe should be allowed
        assert cb.allow_request() is True

        # Third request exceeds probe limit in HALF_OPEN
        assert cb.allow_request() is False

    def test_half_open_success_recovers_to_closed(self):
        cb = CircuitBreaker("test_service", failure_threshold=2, cooldown_seconds=0.05, half_open_probes=1)
        cb.record_failure(RuntimeError("Err 1"))
        cb.record_failure(RuntimeError("Err 2"))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.06)
        assert cb.allow_request() is True  # enters HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

        # Successful probe recovers the breaker
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.allow_request() is True

    def test_half_open_failure_returns_to_open(self):
        cb = CircuitBreaker("test_service", failure_threshold=2, cooldown_seconds=0.05, half_open_probes=1)
        cb.record_failure(RuntimeError("Err 1"))
        cb.record_failure(RuntimeError("Err 2"))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.06)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

        # Failed probe reopens breaker
        cb.record_failure(RuntimeError("Probe failed"))
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_validation_and_captcha_do_not_trip_breaker(self):
        cb = CircuitBreaker("test_service", failure_threshold=2, cooldown_seconds=1.0)

        # Validation errors are client faults, not service health failures
        cb.record_failure(ActionValidationError("Bad query parameter"))
        cb.record_failure(ActionValidationError("Missing field"))
        cb.record_failure(CaptchaChallengeError("Bot challenge"))
        
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True


class TestCircuitBreakerConcurrency:
    """Verify thread-safety of circuit breaker under concurrent access."""

    def test_concurrent_failures_and_successes(self):
        cb = CircuitBreaker("concurrent_svc", failure_threshold=50, cooldown_seconds=5.0)

        def worker(is_failure: bool):
            for _ in range(25):
                if is_failure:
                    cb.record_failure(RuntimeError("Thread error"))
                else:
                    cb.record_success()

        threads = []
        for i in range(4):
            t = threading.Thread(target=worker, args=(i % 2 == 0,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # State and metrics must remain consistent without crashes or deadlocks
        metrics = cb.get_metrics()
        assert metrics["total_calls"] == 100
        assert metrics["total_failures"] == 50
        assert metrics["state"] in ("closed", "open", "half_open")


class TestCircuitBreakerRegistry:
    """Verify registry singleton and metrics management."""

    def test_registry_get_and_reset(self):
        b1 = CircuitBreakerRegistry.get("svc_alpha", failure_threshold=4)
        b2 = CircuitBreakerRegistry.get("svc_alpha")
        assert b1 is b2

        b1.record_failure(RuntimeError("Alpha failure"))
        metrics = CircuitBreakerRegistry.get_all_metrics()
        assert "svc_alpha" in metrics
        assert metrics["svc_alpha"]["failure_count"] == 1

        CircuitBreakerRegistry.reset_all()
        assert b1.failure_count == 0
        assert b1.state == CircuitState.CLOSED
