"""
Verification interface.

Verifies whether an action produced the expected result.  The
orchestrator must not assume success just because a tool returned
without an exception.

The LLM is NOT used as the sole mechanism for verifying its own
actions.  Deterministic verification is the baseline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.agent.models import (
    Observation,
    PlannerResponse,
    ToolResult,
    VerificationResult,
)


class BaseVerifier(ABC):
    """
    Abstract base class for action verification.

    Implementers compare the before/after observations and tool result
    to determine whether the action achieved its expected outcome.
    """

    @abstractmethod
    async def verify(
        self,
        action: PlannerResponse,
        tool_result: ToolResult,
        observation_before: Optional[Observation],
        observation_after: Optional[Observation],
        expected_result: Optional[str],
    ) -> VerificationResult:
        """
        Verify whether the action succeeded.

        Args:
            action: The planned action that was executed.
            tool_result: The normalised tool execution result.
            observation_before: Environment state before the action.
            observation_after: Environment state after the action.
            expected_result: What the planner expected to happen.

        Returns:
            A VerificationResult with success/failure and explanation.
        """
        ...


class DeterministicVerifier(BaseVerifier):
    """
    Deterministic verifier for Phase 3.

    Uses simple, rules-based checks:
        - If the tool reported failure, verification fails.
        - If the tool reported success, verification succeeds.
        - Confidence is 1.0 for deterministic checks.

    More sophisticated verification (visual, DOM-based, LLM-assisted)
    belongs to later phases.
    """

    async def verify(
        self,
        action: PlannerResponse,
        tool_result: ToolResult,
        observation_before: Optional[Observation],
        observation_after: Optional[Observation],
        expected_result: Optional[str],
    ) -> VerificationResult:
        # Primary signal: did the tool report success?
        if not tool_result.success:
            return VerificationResult(
                success=False,
                confidence=1.0,
                explanation=f"Tool '{tool_result.tool_name}' reported failure",
                mismatch=tool_result.error_message,
            )

        # If no expected result specified, trust the tool's success signal
        if not expected_result:
            return VerificationResult(
                success=True,
                confidence=0.8,
                explanation=(
                    f"Tool '{tool_result.tool_name}' reported success. "
                    "No expected-result specification to verify against."
                ),
            )

        # Basic check: expected result is stated, tool succeeded
        return VerificationResult(
            success=True,
            confidence=0.7,
            explanation=(
                f"Tool '{tool_result.tool_name}' reported success. "
                f"Expected: '{expected_result}'. "
                "Deterministic verification cannot fully verify semantic expectations."
            ),
        )


class AlwaysFailVerifier(BaseVerifier):
    """Test helper: always reports verification failure."""

    async def verify(
        self,
        action: PlannerResponse,
        tool_result: ToolResult,
        observation_before: Optional[Observation],
        observation_after: Optional[Observation],
        expected_result: Optional[str],
    ) -> VerificationResult:
        return VerificationResult(
            success=False,
            confidence=1.0,
            explanation="AlwaysFailVerifier: forced failure for testing",
            mismatch="Forced verification failure",
        )
