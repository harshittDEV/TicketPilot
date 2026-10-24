"""
Central Recovery Policy and Bounded Retry Engine (Phase 6).

Responsibilities:
1. Deterministically evaluates errors using the standardized taxonomy.
2. Calculates bounded exponential backoff with configurable limits.
3. Enforces execution deadlines and retry budgets.
4. Prevents blind retries for non-idempotent operations with uncertain outcomes.
5. Emits structured recovery decisions (RETRY, PAUSE_FOR_HUMAN, FAIL_SAFELY, STOP_UNCERTAIN).
6. Supports pluggable sleep mechanisms so unit tests execute deterministically in 0s.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional, Protocol, runtime_checkable

from app.agent.recovery.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from app.agent.recovery.errors import (
    ClassifiedRecoveryError,
    OperationTimeoutError,
    UnknownOutcomeError,
    classify_exception,
)
from app.agent.recovery.idempotency import is_action_idempotent

logger = logging.getLogger(__name__)


# ── Sleeper Abstraction for Deterministic Testing ────────────────────

@runtime_checkable
class Sleeper(Protocol):
    """Protocol for waiting periods during backoff."""
    async def sleep(self, seconds: float) -> None:
        ...


class AsyncioSleeper:
    """Standard production sleeper backed by asyncio.sleep."""
    async def sleep(self, seconds: float) -> None:
        if seconds > 0:
            await asyncio.sleep(seconds)


class ZeroSleeper:
    """Test double sleeper that records sleep calls without blocking."""
    def __init__(self) -> None:
        self.sleep_calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)

    @property
    def total_slept(self) -> float:
        return sum(self.sleep_calls)

    @property
    def call_count(self) -> int:
        return len(self.sleep_calls)


# ── Decision Model ───────────────────────────────────────────────────

class RecoveryAction(str, Enum):
    """Decision produced by the recovery policy."""
    RETRY = "retry"
    PAUSE_FOR_HUMAN = "pause_for_human"
    FAIL_SAFELY = "fail_safely"
    STOP_UNCERTAIN = "stop_uncertain"
    RE_OBSERVE = "re_observe"


@dataclass
class RecoveryDecision:
    """Structured decision returned by the recovery engine."""
    action: RecoveryAction
    backoff_seconds: float = 0.0
    attempt: int = 1
    max_attempts: int = 3
    reason: str = ""
    classified_error: Optional[ClassifiedRecoveryError] = None

    @property
    def requires_human(self) -> bool:
        if self.action in (RecoveryAction.PAUSE_FOR_HUMAN, RecoveryAction.STOP_UNCERTAIN):
            return True
        return bool(self.classified_error and self.classified_error.requires_human)

    @property
    def attempt_number(self) -> int:
        return self.attempt


# ── Central Recovery Policy ──────────────────────────────────────────

class RecoveryPolicy:
    """
    Central recovery policy coordinating retry budgets, backoff, and handoffs.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        initial_backoff: float = 0.5,
        initial_backoff_seconds: Optional[float] = None,
        backoff_multiplier: float = 2.0,
        max_backoff: float = 5.0,
        max_backoff_seconds: Optional[float] = None,
        max_cumulative_retry_time: float = 30.0,
        max_cumulative_seconds: Optional[float] = None,
        sleeper: Optional[Sleeper] = None,
    ) -> None:
        init_bo = initial_backoff_seconds if initial_backoff_seconds is not None else initial_backoff
        max_bo = max_backoff_seconds if max_backoff_seconds is not None else max_backoff
        max_cum = max_cumulative_seconds if max_cumulative_seconds is not None else max_cumulative_retry_time

        self.max_attempts = max(1, max_attempts)
        self.initial_backoff = max(0.0, init_bo)
        self.backoff_multiplier = max(1.0, backoff_multiplier)
        self.max_backoff = max(self.initial_backoff, max_bo)
        self.max_cumulative_retry_time = max(1.0, max_cum)
        self.sleeper: Sleeper = sleeper or AsyncioSleeper()

    def compute_backoff(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """
        Compute bounded exponential backoff for the given attempt.

        Respects explicit retry_after if within max_backoff limit.
        """
        if retry_after is not None and retry_after > 0:
            return min(float(retry_after), self.max_backoff)

        # Exponential: initial * (multiplier ^ (attempt - 1))
        factor = self.backoff_multiplier ** max(0, attempt - 1)
        raw_backoff = self.initial_backoff * factor
        return min(raw_backoff, self.max_backoff)

    calculate_backoff = compute_backoff

    def evaluate(
        self,
        error: ClassifiedRecoveryError,
        *,
        attempt: int,
        elapsed_retry_time: float = 0.0,
        is_idempotent: bool = True,
        is_cancelled: bool = False,
    ) -> RecoveryDecision:
        """
        Evaluate an error and return a deterministic RecoveryDecision.
        """
        # 1. External cancellation overrides all
        if is_cancelled:
            return RecoveryDecision(
                action=RecoveryAction.FAIL_SAFELY,
                attempt=attempt,
                max_attempts=self.max_attempts,
                reason="Operation cancelled by user or context",
                classified_error=error,
            )

        # 2. Uncertain outcome on non-idempotent action must not be retried blindly
        if error.is_uncertain_outcome and not is_idempotent:
            logger.warning(
                "Recovery policy: ambiguous outcome on non-idempotent action. Stopping repetition [%s]",
                error.code,
            )
            return RecoveryDecision(
                action=RecoveryAction.STOP_UNCERTAIN,
                attempt=attempt,
                max_attempts=self.max_attempts,
                reason="Uncertain outcome on non-idempotent action; repetition prohibited",
                classified_error=error,
            )

        # 3. CAPTCHA, session expiration, and human gates require immediate pause
        if error.requires_human:
            logger.info("Recovery policy: pausing for human intervention [%s]", error.code)
            return RecoveryDecision(
                action=RecoveryAction.PAUSE_FOR_HUMAN,
                attempt=attempt,
                max_attempts=self.max_attempts,
                reason=f"Human intervention required: {error.message}",
                classified_error=error,
            )

        # 4. Explicitly unrecoverable errors (validation errors, bad credentials)
        if not error.recoverable:
            logger.info("Recovery policy: unrecoverable error [%s]", error.code)
            return RecoveryDecision(
                action=RecoveryAction.FAIL_SAFELY,
                attempt=attempt,
                max_attempts=self.max_attempts,
                reason=f"Unrecoverable [{error.code}] error: {error.message}",
                classified_error=error,
            )

        # 5. Check retry budget exhaustion
        if attempt >= self.max_attempts:
            logger.warning(
                "Recovery policy: retry budget exhausted (%d/%d attempts) [%s]",
                attempt,
                self.max_attempts,
                error.code,
            )
            return RecoveryDecision(
                action=RecoveryAction.FAIL_SAFELY,
                attempt=attempt,
                max_attempts=self.max_attempts,
                reason=f"Retry budget exhausted after {attempt} attempt(s)",
                classified_error=error,
            )

        # 6. Check explicit Retry-After against remaining execution deadline
        if error.retry_after_seconds is not None:
            remaining_time = self.max_cumulative_retry_time - elapsed_retry_time
            if error.retry_after_seconds > remaining_time:
                logger.warning(
                    "Recovery policy: required wait (%.1fs) exceeds remaining execution deadline (%.1fs)",
                    error.retry_after_seconds,
                    remaining_time,
                )
                return RecoveryDecision(
                    action=RecoveryAction.FAIL_SAFELY,
                    attempt=attempt,
                    max_attempts=self.max_attempts,
                    reason=f"Required wait ({error.retry_after_seconds:.1f}s) exceeds remaining execution deadline ({remaining_time:.1f}s)",
                    classified_error=error,
                )

        # 7. Calculate backoff
        backoff = self.compute_backoff(attempt, error.retry_after_seconds)

        # 8. Check cumulative retry deadline
        if (elapsed_retry_time + backoff) > self.max_cumulative_retry_time:
            logger.warning(
                "Recovery policy: cumulative retry deadline exceeded (%.1fs + %.1fs > %.1fs)",
                elapsed_retry_time,
                backoff,
                self.max_cumulative_retry_time,
            )
            return RecoveryDecision(
                action=RecoveryAction.FAIL_SAFELY,
                attempt=attempt,
                max_attempts=self.max_attempts,
                reason="Cumulative retry deadline exceeded",
                classified_error=error,
            )

        # 8. Retry allowed
        logger.info(
            "Recovery policy: scheduling retry %d/%d after %.2fs backoff [%s]",
            attempt + 1,
            self.max_attempts,
            backoff,
            error.code,
        )
        decision = RecoveryDecision(
            action=RecoveryAction.RETRY,
            backoff_seconds=backoff,
            attempt=attempt,
            max_attempts=self.max_attempts,
            reason=f"Retry attempt {attempt + 1} scheduled",
            classified_error=error,
        )
        try:
            from app.services.audit_service import get_audit_service
            get_audit_service().record_recovery_event(
                task_id=None,
                run_id=None,
                event_type="recovery.retry_scheduled",
                error_category=error.category.value,
                error_code=error.code,
                decision="RETRY",
                backoff_seconds=backoff,
                attempt=attempt,
            )
        except Exception:
            pass
        return decision

    async def execute_with_recovery(
        self,
        operation: Callable[[], Coroutine[Any, Any, Any]],
        *,
        action_type: str = "operation",
        circuit_breaker: Optional[CircuitBreaker] = None,
        is_idempotent: Optional[bool] = None,
        on_retry: Optional[Callable[[RecoveryDecision], None]] = None,
        is_cancelled_fn: Optional[Callable[[], bool]] = None,
    ) -> Any:
        """
        Execute an asynchronous operation governed by the recovery policy.

        Applies circuit breaker checks, error classification, bounded exponential
        backoff, and interruptible sleep.
        """
        idempotent = is_idempotent if is_idempotent is not None else is_action_idempotent(action_type)
        attempt = 1
        elapsed_retry_time = 0.0

        while True:
            # 1. Check circuit breaker if configured
            if circuit_breaker is not None:
                await circuit_breaker.check_available()

            try:
                result = await operation()
                if circuit_breaker is not None:
                    circuit_breaker.record_success()
                return result

            except Exception as exc:
                if circuit_breaker is not None:
                    circuit_breaker.record_failure(exc)

                # Classify the failure
                classified = classify_exception(
                    exc, action_type=action_type, is_idempotent=idempotent
                )

                is_cancelled = is_cancelled_fn() if is_cancelled_fn else False
                decision = self.evaluate(
                    classified,
                    attempt=attempt,
                    elapsed_retry_time=elapsed_retry_time,
                    is_idempotent=idempotent,
                    is_cancelled=is_cancelled,
                )

                if on_retry:
                    on_retry(decision)

                if decision.action == RecoveryAction.RETRY:
                    # Interruptible sleep
                    await self.sleeper.sleep(decision.backoff_seconds)
                    elapsed_retry_time += decision.backoff_seconds
                    attempt += 1
                    continue

                # Non-retry decision: re-raise classified error
                raise classified
