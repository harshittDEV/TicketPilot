"""
Execution-run state machine.

Defines the dedicated run lifecycle — separate from the task lifecycle.
All run state transitions are validated centrally through this module.

A task may be RUNNING while its associated run is temporarily PAUSED.
The task state machine (``task_state_machine.py``) is never bypassed
or duplicated here; task-level transitions remain the responsibility
of ``TaskService``.
"""

from __future__ import annotations

from enum import Enum

from app.core.exceptions import AppException
from fastapi import status as http_status


class RunStatus(str, Enum):
    """All possible lifecycle states for an execution run."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# States from which no further transition is allowed
TERMINAL_RUN_STATES: frozenset[RunStatus] = frozenset({
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
})

# States considered "active" (non-terminal)
ACTIVE_RUN_STATES: frozenset[RunStatus] = frozenset({
    RunStatus.PENDING,
    RunStatus.RUNNING,
    RunStatus.PAUSED,
    RunStatus.WAITING_FOR_HUMAN,
})

# States that permit cancellation
CANCELLABLE_RUN_STATES: frozenset[RunStatus] = frozenset({
    RunStatus.PENDING,
    RunStatus.RUNNING,
    RunStatus.PAUSED,
    RunStatus.WAITING_FOR_HUMAN,
})

# States that permit pausing
PAUSABLE_RUN_STATES: frozenset[RunStatus] = frozenset({
    RunStatus.RUNNING,
})

# ── Transition policy ────────────────────────────────────────────
RUN_TRANSITION_POLICY: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({
        RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED,
    }),
    RunStatus.RUNNING: frozenset({
        RunStatus.PAUSED,
        RunStatus.WAITING_FOR_HUMAN,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    }),
    RunStatus.PAUSED: frozenset({
        RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED,
    }),
    RunStatus.WAITING_FOR_HUMAN: frozenset({
        RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED,
    }),
    # Terminal states — no transitions allowed
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}


# ── Exceptions ───────────────────────────────────────────────────

class InvalidRunTransitionError(AppException):
    """Raised when a run state transition violates the transition policy."""

    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            message=(
                f"Invalid run state transition: {current} → {requested}. "
                f"This transition is not permitted by the run lifecycle policy."
            ),
            code="INVALID_RUN_TRANSITION",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class RunNotFoundError(AppException):
    """Raised when an execution run cannot be found by its identifier."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            message=f"Execution run not found: {run_id}",
            code="RUN_NOT_FOUND",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )


class RunStateConflictError(AppException):
    """Raised on optimistic locking conflict (stale version)."""

    def __init__(self, run_id: str) -> None:
        super().__init__(
            message=(
                f"Execution run '{run_id}' was modified by another request. "
                f"Reload the run and retry."
            ),
            code="RUN_STATE_CONFLICT",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class DuplicateActiveRunError(AppException):
    """Raised when attempting to create a second active run for a task."""

    def __init__(self, task_id: str, existing_run_id: str) -> None:
        super().__init__(
            message=(
                f"Task '{task_id}' already has an active run: {existing_run_id}. "
                f"Only one active run per task is allowed."
            ),
            code="DUPLICATE_ACTIVE_RUN",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class RunValidationError(AppException):
    """Raised when run input validation fails at the service level."""

    def __init__(self, message: str = "Run validation failed") -> None:
        super().__init__(
            message=message,
            code="RUN_VALIDATION_ERROR",
            status_code=getattr(http_status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        )


# ── Validation ───────────────────────────────────────────────────

def validate_run_transition(current: RunStatus, target: RunStatus) -> None:
    """
    Validate that transitioning from *current* to *target* is allowed.

    Raises:
        InvalidRunTransitionError: If the transition is not permitted.
    """
    allowed = RUN_TRANSITION_POLICY.get(current, frozenset())
    if target not in allowed:
        raise InvalidRunTransitionError(current.value, target.value)
