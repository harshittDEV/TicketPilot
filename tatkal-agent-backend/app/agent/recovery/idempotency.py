"""
Action Idempotency and Outcome Classification (Phase 6).

Distinguishes between:
1. Idempotent actions (safe to repeat without unintended side effects)
2. Non-idempotent actions (repeated execution may cause duplicate submissions or clicks)
3. Critical irreversible actions (payments, booking submissions - blind repetition strictly forbidden)
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class OperationOutcome(str, Enum):
    """Classification of an operation's completion certainty."""
    CONFIRMED_SUCCESS = "confirmed_success"
    CONFIRMED_FAILURE = "confirmed_failure"
    UNKNOWN_OUTCOME = "unknown_outcome"


# Safe, read-only actions that produce no persistent side effects
IDEMPOTENT_ACTIONS: frozenset[str] = frozenset({
    "navigate",
    "inspect",
    "extract_text",
    "get_url_and_title",
    "screenshot",
    "find_trains",
    "calculate_schedule",
    "health",
    "session_status",
    "check_authorization",
    "redact",
})

# Actions that submit data or trigger state changes
NON_IDEMPOTENT_ACTIONS: frozenset[str] = frozenset({
    "click",
    "type_text",
    "press_key",
    "execute_booking",
    "schedule_run",
    "cancel_run",
})

# High-risk financial or terminal booking actions requiring strict idempotency
CRITICAL_ACTIONS: frozenset[str] = frozenset({
    "payment_approval",
    "booking_submission",
    "confirm_payment",
    "pay",
    "submit_order",
})


def is_action_idempotent(action_type: str) -> bool:
    """Return True if the action is safe to retry without side effects."""
    action = action_type.lower().strip()
    return action in IDEMPOTENT_ACTIONS and action not in CRITICAL_ACTIONS


def is_action_critical(action_type: str) -> bool:
    """Return True if the action involves financial or irreversible side effects."""
    action = action_type.lower().strip()
    return action in CRITICAL_ACTIONS or any(c in action for c in ("pay", "book", "submit"))


def classify_outcome(
    success: bool,
    *,
    is_idempotent: bool,
    timed_out: bool = False,
    connection_lost: bool = False,
) -> OperationOutcome:
    """
    Determine whether an outcome is confirmed or ambiguous.

    If a non-idempotent action experiences a timeout or network drop, the outcome
    is marked UNKNOWN_OUTCOME.
    """
    if success:
        return OperationOutcome.CONFIRMED_SUCCESS

    if (timed_out or connection_lost) and not is_idempotent:
        return OperationOutcome.UNKNOWN_OUTCOME

    return OperationOutcome.CONFIRMED_FAILURE
