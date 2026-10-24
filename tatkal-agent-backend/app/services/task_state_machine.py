"""
Formal task state machine.

Defines:
    - ``TaskStatus`` enum with all lifecycle states.
    - ``TRANSITION_POLICY`` mapping each state to its allowed next states.
    - ``validate_transition()`` to enforce the policy.
    - ``TERMINAL_STATES`` that cannot be changed once reached.

The transition policy is centralised here — route handlers and services
must not scatter transition conditions.
"""

from __future__ import annotations

from enum import Enum

from app.core.exceptions import AppException
from fastapi import status as http_status


class TaskStatus(str, Enum):
    """All possible lifecycle states for a task."""
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    RECOVERING = "RECOVERING"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    AWAITING_PAYMENT_APPROVAL = "AWAITING_PAYMENT_APPROVAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# States from which no further transition is allowed
TERMINAL_STATES: frozenset[TaskStatus] = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
})

# States that permit cancellation
CANCELLABLE_STATES: frozenset[TaskStatus] = frozenset({
    TaskStatus.CREATED,
    TaskStatus.READY,
    TaskStatus.RUNNING,
    TaskStatus.RECOVERING,
    TaskStatus.AWAITING_HUMAN,
    TaskStatus.AWAITING_PAYMENT_APPROVAL,
})

# ── Transition policy ────────────────────────────────────────────
TRANSITION_POLICY: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.CREATED: frozenset({
        TaskStatus.READY, TaskStatus.CANCELLED, TaskStatus.FAILED,
    }),
    TaskStatus.READY: frozenset({
        TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED,
    }),
    TaskStatus.RUNNING: frozenset({
        TaskStatus.RECOVERING,
        TaskStatus.AWAITING_HUMAN,
        TaskStatus.AWAITING_PAYMENT_APPROVAL,
        TaskStatus.VERIFYING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }),
    TaskStatus.RECOVERING: frozenset({
        TaskStatus.RUNNING,
        TaskStatus.AWAITING_HUMAN,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }),
    TaskStatus.AWAITING_HUMAN: frozenset({
        TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED,
    }),
    TaskStatus.AWAITING_PAYMENT_APPROVAL: frozenset({
        TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED,
    }),
    TaskStatus.VERIFYING: frozenset({
        TaskStatus.COMPLETED,
        TaskStatus.RECOVERING,
        TaskStatus.AWAITING_HUMAN,
        TaskStatus.FAILED,
    }),
    # Terminal states — no transitions allowed
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


# ── Exceptions ───────────────────────────────────────────────────

class InvalidTaskTransitionError(AppException):
    """Raised when a state transition violates the transition policy."""

    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            message=(
                f"Invalid state transition: {current} → {requested}. "
                f"This transition is not permitted by the task lifecycle policy."
            ),
            code="INVALID_TASK_TRANSITION",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class TaskNotFoundError(AppException):
    """Raised when a task cannot be found by its identifier."""

    def __init__(self, task_id: str) -> None:
        super().__init__(
            message=f"Task not found: {task_id}",
            code="TASK_NOT_FOUND",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )


class TaskStateConflictError(AppException):
    """Raised on optimistic locking conflict (stale version)."""

    def __init__(self, task_id: str) -> None:
        super().__init__(
            message=(
                f"Task '{task_id}' was modified by another request. "
                f"Reload the task and retry."
            ),
            code="TASK_STATE_CONFLICT",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class TaskValidationError(AppException):
    """Raised when task input validation fails at the service level."""

    def __init__(self, message: str = "Task validation failed") -> None:
        super().__init__(
            message=message,
            code="TASK_VALIDATION_ERROR",
            status_code=getattr(http_status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        )


# ── Validation ───────────────────────────────────────────────────

def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    """
    Validate that transitioning from *current* to *target* is allowed.

    Raises:
        InvalidTaskTransitionError: If the transition is not permitted.
    """
    allowed = TRANSITION_POLICY.get(current, frozenset())
    if target not in allowed:
        raise InvalidTaskTransitionError(current.value, target.value)
