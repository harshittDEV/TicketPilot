"""Tests for the Task state machine."""

import pytest

from app.services.task_state_machine import (
    CANCELLABLE_STATES,
    TERMINAL_STATES,
    TRANSITION_POLICY,
    InvalidTaskTransitionError,
    TaskStatus,
    validate_transition,
)


class TestTaskStatusEnum:
    """Verify all expected states exist."""

    def test_all_states_defined(self):
        expected = {
            "CREATED", "READY", "RUNNING", "RECOVERING",
            "AWAITING_HUMAN", "AWAITING_PAYMENT_APPROVAL", "VERIFYING",
            "COMPLETED", "FAILED", "CANCELLED",
        }
        actual = {s.value for s in TaskStatus}
        assert actual == expected

    def test_terminal_states(self):
        assert TERMINAL_STATES == {
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED,
        }


class TestTransitionPolicy:
    """Verify every allowed transition succeeds and invalid ones are rejected."""

    @pytest.mark.parametrize("current,target", [
        (TaskStatus.CREATED, TaskStatus.READY),
        (TaskStatus.CREATED, TaskStatus.CANCELLED),
        (TaskStatus.CREATED, TaskStatus.FAILED),
        (TaskStatus.READY, TaskStatus.RUNNING),
        (TaskStatus.READY, TaskStatus.CANCELLED),
        (TaskStatus.READY, TaskStatus.FAILED),
        (TaskStatus.RUNNING, TaskStatus.RECOVERING),
        (TaskStatus.RUNNING, TaskStatus.AWAITING_HUMAN),
        (TaskStatus.RUNNING, TaskStatus.AWAITING_PAYMENT_APPROVAL),
        (TaskStatus.RUNNING, TaskStatus.VERIFYING),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED),
        (TaskStatus.RUNNING, TaskStatus.FAILED),
        (TaskStatus.RUNNING, TaskStatus.CANCELLED),
        (TaskStatus.RECOVERING, TaskStatus.RUNNING),
        (TaskStatus.RECOVERING, TaskStatus.AWAITING_HUMAN),
        (TaskStatus.RECOVERING, TaskStatus.FAILED),
        (TaskStatus.RECOVERING, TaskStatus.CANCELLED),
        (TaskStatus.AWAITING_HUMAN, TaskStatus.RUNNING),
        (TaskStatus.AWAITING_HUMAN, TaskStatus.FAILED),
        (TaskStatus.AWAITING_HUMAN, TaskStatus.CANCELLED),
        (TaskStatus.AWAITING_PAYMENT_APPROVAL, TaskStatus.RUNNING),
        (TaskStatus.AWAITING_PAYMENT_APPROVAL, TaskStatus.FAILED),
        (TaskStatus.AWAITING_PAYMENT_APPROVAL, TaskStatus.CANCELLED),
        (TaskStatus.VERIFYING, TaskStatus.COMPLETED),
        (TaskStatus.VERIFYING, TaskStatus.RECOVERING),
        (TaskStatus.VERIFYING, TaskStatus.AWAITING_HUMAN),
        (TaskStatus.VERIFYING, TaskStatus.FAILED),
    ])
    def test_allowed_transitions(self, current, target):
        """Each allowed transition must not raise."""
        validate_transition(current, target)  # Should not raise

    @pytest.mark.parametrize("current,target", [
        (TaskStatus.CREATED, TaskStatus.COMPLETED),
        (TaskStatus.CREATED, TaskStatus.RUNNING),
        (TaskStatus.RUNNING, TaskStatus.CREATED),
        (TaskStatus.COMPLETED, TaskStatus.RUNNING),
        (TaskStatus.COMPLETED, TaskStatus.CREATED),
        (TaskStatus.FAILED, TaskStatus.RUNNING),
        (TaskStatus.FAILED, TaskStatus.CREATED),
        (TaskStatus.CANCELLED, TaskStatus.RUNNING),
        (TaskStatus.CANCELLED, TaskStatus.CREATED),
        (TaskStatus.READY, TaskStatus.COMPLETED),
    ])
    def test_invalid_transitions_rejected(self, current, target):
        """Invalid transitions must raise InvalidTaskTransitionError."""
        with pytest.raises(InvalidTaskTransitionError):
            validate_transition(current, target)

    def test_terminal_states_have_no_outgoing(self):
        """Terminal states must have empty allowed-transitions sets."""
        for state in TERMINAL_STATES:
            assert TRANSITION_POLICY[state] == frozenset()

    def test_every_state_has_a_policy_entry(self):
        """Every TaskStatus must appear as a key in the policy."""
        for state in TaskStatus:
            assert state in TRANSITION_POLICY
