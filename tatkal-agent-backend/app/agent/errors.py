"""
Structured orchestration errors.

These exceptions are raised within the agent orchestration package.
They extend the centralised AppException hierarchy so the global
exception handlers produce consistent API error responses.
"""

from __future__ import annotations

from app.core.exceptions import AppException
from fastapi import status as http_status


class OrchestrationError(AppException):
    """Base error for orchestration failures."""

    def __init__(
        self,
        message: str = "An orchestration error occurred",
        code: str = "ORCHESTRATION_ERROR",
        status_code: int = http_status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code)


class PlannerError(OrchestrationError):
    """Raised when the planner produces an invalid or unparseable response."""

    def __init__(self, message: str = "Planner returned an invalid response") -> None:
        super().__init__(
            message=message,
            code="PLANNER_ERROR",
            status_code=http_status.HTTP_502_BAD_GATEWAY,
        )


class PlannerTimeoutError(OrchestrationError):
    """Raised when the planner does not respond within the timeout."""

    def __init__(self, timeout_seconds: float = 0) -> None:
        super().__init__(
            message=f"Planner timed out after {timeout_seconds:.1f}s",
            code="PLANNER_TIMEOUT",
            status_code=http_status.HTTP_504_GATEWAY_TIMEOUT,
        )


class ToolResolutionError(OrchestrationError):
    """Raised when the requested tool is not registered."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            message=f"Tool '{tool_name}' is not registered in the integration registry",
            code="TOOL_NOT_FOUND",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )


class ToolExecutionError(OrchestrationError):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, reason: str = "unknown") -> None:
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {reason}",
            code="TOOL_EXECUTION_FAILED",
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class ActionLimitExceededError(OrchestrationError):
    """Raised when the maximum number of actions per run is exceeded."""

    def __init__(self, max_steps: int) -> None:
        super().__init__(
            message=f"Run exceeded the maximum action limit of {max_steps} steps",
            code="ACTION_LIMIT_EXCEEDED",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class RunDeadlineExceededError(OrchestrationError):
    """Raised when the overall run duration deadline is exceeded."""

    def __init__(self) -> None:
        super().__init__(
            message="Run exceeded the maximum allowed duration",
            code="RUN_DEADLINE_EXCEEDED",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class VerificationFailedError(OrchestrationError):
    """Raised when action verification fails and the orchestrator cannot proceed."""

    def __init__(self, explanation: str = "") -> None:
        msg = "Action verification failed"
        if explanation:
            msg += f": {explanation}"
        super().__init__(
            message=msg,
            code="VERIFICATION_FAILED",
            status_code=http_status.HTTP_409_CONFLICT,
        )


class RunCancelledError(OrchestrationError):
    """Raised when the run is cancelled during execution."""

    def __init__(self, run_id: str = "") -> None:
        super().__init__(
            message=f"Run '{run_id}' was cancelled" if run_id else "Run was cancelled",
            code="RUN_CANCELLED",
            status_code=http_status.HTTP_409_CONFLICT,
        )
