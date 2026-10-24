"""
Concurrency-safe in-process Circuit Breaker for external integrations (Phase 6).

Implements the three standard states:
- CLOSED: Normal operation. Failures are tracked within a rolling time window.
- OPEN: The dependency is failing; requests are rejected immediately without calling it.
- HALF_OPEN: Cooldown has passed; a bounded probe is allowed to test for recovery.

Limitations:
- This is a process-local circuit breaker. It maintains in-memory state for the running
  backend worker and does not distribute breaker state across multiple worker processes.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from enum import Enum
from typing import Any, Optional

from app.agent.recovery.errors import (
    ActionValidationError,
    CaptchaChallengeError,
    ClassifiedRecoveryError,
    ServiceUnavailableRecoveryError,
)

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Possible operational states of a circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(ServiceUnavailableRecoveryError):
    """Raised when a request is rejected because the circuit breaker is OPEN."""

    def __init__(self, breaker_name: str, cooldown_remaining: float) -> None:
        self.breaker_name = breaker_name
        self.cooldown_remaining = max(0.0, cooldown_remaining)
        super().__init__(
            service_name=breaker_name,
            message=(
                f"Circuit breaker '{breaker_name}' is OPEN. "
                f"Dependency calls deferred for {cooldown_remaining:.1f}s cooldown."
            ),
            safe_context={
                "breaker_name": breaker_name,
                "circuit_state": CircuitState.OPEN.value,
                "cooldown_remaining_seconds": max(0.0, cooldown_remaining),
            },
        )


class CircuitBreaker:
    """
    Thread- and asyncio-safe in-process circuit breaker.

    Guards calls to external integrations and dependencies against cascading failures.
    """

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        half_open_probe_limit: int = 1,
        half_open_probes: Optional[int] = None,
        failure_window_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(0.01, cooldown_seconds)
        self.half_open_probe_limit = max(1, half_open_probes if half_open_probes is not None else half_open_probe_limit)
        self.failure_window_seconds = max(1.0, failure_window_seconds)

        self._state = CircuitState.CLOSED
        self._failures: deque[float] = deque()
        self._opened_at: Optional[float] = None
        self._half_open_probes_active = 0
        self._total_calls = 0
        self._total_failures = 0
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current state of the circuit breaker."""
        with self._lock:
            self._evaluate_state_transition()
            return self._state

    @property
    def failure_count(self) -> int:
        """Current failure count in active window."""
        with self._lock:
            return len(self._failures)

    def _evaluate_state_transition(self) -> None:
        """Internal helper to evaluate cooldown expiry without holding locks."""
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.cooldown_seconds:
                logger.info(
                    "Circuit breaker '%s' cooldown elapsed (%.1fs). Transitioning OPEN -> HALF_OPEN",
                    self.name,
                    elapsed,
                )
                self._state = CircuitState.HALF_OPEN
                self._half_open_probes_active = 0

    @property
    def cooldown_remaining(self) -> float:
        """Return the number of seconds remaining before cooldown expires."""
        with self._lock:
            if self._state != CircuitState.OPEN or self._opened_at is None:
                return 0.0
            elapsed = time.monotonic() - self._opened_at
            return max(0.0, self.cooldown_seconds - elapsed)

    def get_cooldown_remaining(self) -> float:
        return self.cooldown_remaining

    def allow_request(self) -> bool:
        """
        Synchronous check if a request is permitted.

        Returns True if permitted, False if rejected by breaker.
        """
        with self._lock:
            self._evaluate_state_transition()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_probes_active < self.half_open_probe_limit:
                    self._half_open_probes_active += 1
                    logger.info(
                        "Circuit breaker '%s' allowing probe %d/%d in HALF_OPEN state",
                        self.name,
                        self._half_open_probes_active,
                        self.half_open_probe_limit,
                    )
                    return True
                return False

            # CircuitState.OPEN
            return False

    async def check_available(self) -> None:
        """
        Asynchronously verify if request is permitted, raising CircuitBreakerOpenError if OPEN.
        """
        async with self._async_lock:
            allowed = self.allow_request()
            if not allowed:
                raise CircuitBreakerOpenError(self.name, self.cooldown_remaining)

    def record_success(self) -> None:
        """Record a successful dependency invocation."""
        with self._lock:
            self._total_calls += 1
            if self._state == CircuitState.HALF_OPEN:
                logger.info(
                    "Probe successful for circuit breaker '%s'. Transitioning HALF_OPEN -> CLOSED",
                    self.name,
                )
                self._state = CircuitState.CLOSED
                self._failures.clear()
                self._opened_at = None
                self._half_open_probes_active = 0
                try:
                    from app.services.audit_service import get_audit_service
                    get_audit_service().record_circuit_breaker_event(
                        breaker_name=self.name,
                        from_state="HALF_OPEN",
                        to_state="CLOSED",
                    )
                except Exception:
                    pass
            elif self._state == CircuitState.CLOSED:
                # Clear stale failure timestamps
                self._failures.clear()

    def record_failure(self, exc: Optional[Exception] = None) -> None:
        """
        Record a failure from a dependency invocation.

        Excludes non-transient conditions (validation errors, CAPTCHAs) from tripping breaker.
        """
        # Exclude non-dependency failures
        if isinstance(exc, (ActionValidationError, CaptchaChallengeError, ValueError)):
            logger.debug(
                "Circuit breaker '%s' ignoring non-dependency error: %s", self.name, exc
            )
            return

        now = time.monotonic()
        with self._lock:
            self._total_calls += 1
            self._total_failures += 1
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "Probe failed for circuit breaker '%s'. Transitioning HALF_OPEN -> OPEN",
                    self.name,
                )
                self._state = CircuitState.OPEN
                self._opened_at = now
                self._half_open_probes_active = 0
                try:
                    from app.services.audit_service import get_audit_service
                    get_audit_service().record_circuit_breaker_event(
                        breaker_name=self.name,
                        from_state="HALF_OPEN",
                        to_state="OPEN",
                    )
                except Exception:
                    pass
                return

            # Purge failures outside the failure window
            cutoff = now - self.failure_window_seconds
            while self._failures and self._failures[0] < cutoff:
                self._failures.popleft()

            self._failures.append(now)
            failure_count = len(self._failures)

            if failure_count >= self.failure_threshold:
                logger.warning(
                    "Circuit breaker '%s' threshold exceeded (%d/%d failures in %.0fs). Transitioning CLOSED -> OPEN",
                    self.name,
                    failure_count,
                    self.failure_threshold,
                    self.failure_window_seconds,
                )
                self._state = CircuitState.OPEN
                self._opened_at = now
                try:
                    from app.services.audit_service import get_audit_service
                    get_audit_service().record_circuit_breaker_event(
                        breaker_name=self.name,
                        from_state="CLOSED",
                        to_state="OPEN",
                        metrics={"failure_count": failure_count, "failure_threshold": self.failure_threshold},
                    )
                except Exception:
                    pass

    def reset(self) -> None:
        """Reset the circuit breaker to initial CLOSED state (for testing)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures.clear()
            self._opened_at = None
            self._half_open_probes_active = 0

    def get_stats(self) -> dict[str, Any]:
        """Return diagnostic metrics for health and monitoring endpoints."""
        with self._lock:
            self._evaluate_state_transition()
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": len(self._failures),
                "failure_threshold": self.failure_threshold,
                "cooldown_remaining_seconds": self.cooldown_remaining,
                "half_open_probes_active": self._half_open_probes_active,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
            }

    def get_metrics(self) -> dict[str, Any]:
        """Alias for get_stats()."""
        return self.get_stats()


class CircuitBreakerRegistry:
    """Registry maintaining singleton instances of named circuit breakers."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_breaker(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        half_open_probe_limit: int = 1,
    ) -> CircuitBreaker:
        """Get or create a named circuit breaker."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    cooldown_seconds=cooldown_seconds,
                    half_open_probe_limit=half_open_probe_limit,
                )
            return self._breakers[name]

    def _do_reset_all(self) -> None:
        """Reset all registered breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def reset_all(self) -> None:
        self._do_reset_all()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Return diagnostics for all registered circuit breakers."""
        with self._lock:
            return {name: b.get_stats() for name, b in self._breakers.items()}

    @classmethod
    def get(cls, name: str, **kwargs) -> CircuitBreaker:
        return get_circuit_breaker_registry().get_breaker(name, **kwargs)

    @classmethod
    def reset_all(cls) -> None:
        get_circuit_breaker_registry()._do_reset_all()

    @classmethod
    def reset_all_breakers(cls) -> None:
        cls.reset_all()

    @classmethod
    def get_all_metrics(cls) -> dict[str, dict[str, Any]]:
        return get_circuit_breaker_registry().get_all_stats()


# ── Global singleton ─────────────────────────────────────────────────
_circuit_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Return the application-wide circuit breaker registry."""
    global _circuit_registry
    if _circuit_registry is None:
        _circuit_registry = CircuitBreakerRegistry()
    return _circuit_registry
