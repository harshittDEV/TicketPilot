"""
Tests for run state machine — transition policy and validation.
"""

import pytest

from app.services.run_state_machine import (
    ACTIVE_RUN_STATES,
    CANCELLABLE_RUN_STATES,
    RUN_TRANSITION_POLICY,
    TERMINAL_RUN_STATES,
    RunStatus,
    InvalidRunTransitionError,
    validate_run_transition,
)


class TestRunTransitionPolicy:
    """Verify the run state machine's transition policy."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (RunStatus.PENDING, RunStatus.RUNNING),
            (RunStatus.PENDING, RunStatus.CANCELLED),
            (RunStatus.PENDING, RunStatus.FAILED),
            (RunStatus.RUNNING, RunStatus.PAUSED),
            (RunStatus.RUNNING, RunStatus.WAITING_FOR_HUMAN),
            (RunStatus.RUNNING, RunStatus.COMPLETED),
            (RunStatus.RUNNING, RunStatus.FAILED),
            (RunStatus.RUNNING, RunStatus.CANCELLED),
            (RunStatus.PAUSED, RunStatus.RUNNING),
            (RunStatus.PAUSED, RunStatus.CANCELLED),
            (RunStatus.PAUSED, RunStatus.FAILED),
            (RunStatus.WAITING_FOR_HUMAN, RunStatus.RUNNING),
            (RunStatus.WAITING_FOR_HUMAN, RunStatus.CANCELLED),
            (RunStatus.WAITING_FOR_HUMAN, RunStatus.FAILED),
        ],
    )
    def test_allowed_transitions(self, current, target):
        """Every declared allowed transition must pass validation."""
        validate_run_transition(current, target)  # should not raise

    @pytest.mark.parametrize(
        "current,target",
        [
            (RunStatus.PENDING, RunStatus.COMPLETED),
            (RunStatus.PENDING, RunStatus.PAUSED),
            (RunStatus.RUNNING, RunStatus.PENDING),
            (RunStatus.COMPLETED, RunStatus.RUNNING),
            (RunStatus.COMPLETED, RunStatus.PENDING),
            (RunStatus.FAILED, RunStatus.RUNNING),
            (RunStatus.FAILED, RunStatus.PENDING),
            (RunStatus.CANCELLED, RunStatus.RUNNING),
            (RunStatus.CANCELLED, RunStatus.PENDING),
            (RunStatus.PAUSED, RunStatus.COMPLETED),
        ],
    )
    def test_invalid_transitions_rejected(self, current, target):
        """Invalid transitions must raise InvalidRunTransitionError."""
        with pytest.raises(InvalidRunTransitionError):
            validate_run_transition(current, target)

    def test_terminal_states_have_no_outgoing(self):
        """Terminal states must have empty transition sets."""
        for state in TERMINAL_RUN_STATES:
            assert RUN_TRANSITION_POLICY[state] == frozenset()

    def test_every_state_has_a_policy_entry(self):
        """Every RunStatus must have an entry in the transition policy."""
        for state in RunStatus:
            assert state in RUN_TRANSITION_POLICY

    def test_active_and_terminal_are_disjoint(self):
        """Active and terminal state sets must not overlap."""
        assert ACTIVE_RUN_STATES.isdisjoint(TERMINAL_RUN_STATES)

    def test_all_states_are_active_or_terminal(self):
        """Every state must be either active or terminal."""
        all_states = set(RunStatus)
        categorised = ACTIVE_RUN_STATES | TERMINAL_RUN_STATES
        assert all_states == categorised
