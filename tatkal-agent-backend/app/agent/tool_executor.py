"""
Generic tool execution engine.

Reuses the existing ``AgentToolIntegration`` protocol and
``IntegrationRegistry``.  Does NOT create a second registry.

Responsibilities:
    1. Validate the proposed action.
    2. Resolve the requested tool from the registry.
    3. Verify that the tool is available.
    4. Validate the action timeout.
    5. Invoke the adapter.
    6. Normalise the result.
    7. Handle timeout and tool errors.
    8. Return a structured ToolResult.
    9. Enforce action limit and run deadline (via ExecutionContext).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.agent.errors import (
    ActionLimitExceededError,
    RunDeadlineExceededError,
    ToolExecutionError,
    ToolResolutionError,
)
from app.agent.models import ExecutionContext, PlannerResponse, ToolResult
from app.integrations.contracts import (
    AgentToolIntegration,
    ToolAction,
    ToolActionStatus,
    ToolExecutionResult,
)
from app.integrations.registry import IntegrationRegistry
from app.agent.recovery.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry
from app.agent.recovery.errors import (
    ClassifiedRecoveryError,
    OperationTimeoutError,
    classify_exception,
)
from app.agent.recovery.idempotency import is_action_idempotent
from app.agent.recovery.policy import RecoveryAction, RecoveryPolicy

logger = logging.getLogger(__name__)



class ToolExecutor:
    """
    Generic tool execution service.

    Uses the existing IntegrationRegistry to resolve tool adapters.
    Enforces execution limits and normalises results.
    """

    def __init__(
        self,
        registry: IntegrationRegistry,
        *,
        default_timeout: float = 30.0,
        max_timeout: float = 120.0,
        recovery_policy: Any | None = None,
        circuit_breaker_registry: Any | None = None,
        circuit_breakers: Any | None = None,
    ) -> None:
        self._registry = registry
        self._default_timeout = default_timeout
        self._max_timeout = max_timeout
        self._recovery_policy = recovery_policy
        self._circuit_breaker_registry = circuit_breaker_registry
        self._circuit_breakers = circuit_breakers or {}


    def validate_action(
        self,
        plan: PlannerResponse,
        context: ExecutionContext,
    ) -> None:
        """
        Validate that the proposed action can be executed.

        Checks:
            - The run is within step and deadline limits.
            - The tool name is provided for tool actions.
            - The tool is registered.

        Raises:
            ActionLimitExceededError: Step limit exceeded.
            RunDeadlineExceededError: Run deadline exceeded.
            ToolResolutionError: Tool not registered.
        """
        if not context.is_within_limits():
            if context.action_count >= context.max_steps:
                raise ActionLimitExceededError(context.max_steps)
            raise RunDeadlineExceededError()

        from app.agent.models import ActionType
        if plan.action_type == ActionType.TOOL_ACTION:
            if not plan.tool_name:
                raise ToolExecutionError("unknown", "tool_name is required for TOOL_ACTION")
            if not self._registry.is_registered(plan.tool_name):
                raise ToolResolutionError(plan.tool_name)

    def _resolve_tool(self, tool_name: str) -> AgentToolIntegration:
        """
        Resolve a tool adapter from the registry.

        Raises:
            ToolResolutionError: If the tool is not registered.
        """
        if hasattr(self._registry, "is_tool_registered") and self._registry.is_tool_registered(tool_name):
            return self._registry.get_tool(tool_name)
        if self._registry.is_registered(tool_name):
            return self._registry.get(tool_name)
        raise ToolResolutionError(tool_name)

    def _build_tool_action(self, plan: PlannerResponse) -> ToolAction:
        """Build a ToolAction from the planner response."""
        timeout = plan.action_parameters.get(
            "timeout_seconds", self._default_timeout
        )
        # Clamp timeout
        timeout = max(1.0, min(float(timeout), self._max_timeout))

        return ToolAction(
            action_type=plan.action_parameters.get("action_type", plan.tool_name or "unknown"),
            parameters=plan.action_parameters,
            timeout_seconds=timeout,
        )

    async def execute(
        self,
        plan: PlannerResponse,
        context: ExecutionContext,
    ) -> ToolResult:
        """
        Execute a tool action and return a normalised result.

        Steps:
            1. Validate limits.
            2. Resolve tool.
            3. Check tool availability and validate parameters.
            4. Build ToolAction.
            5. Invoke with timeout.
            6. Normalise result with structured status.
        """
        from app.agent.models import ActionType

        # Non-tool actions return a synthetic result
        if plan.action_type != ActionType.TOOL_ACTION:
            return ToolResult(
                tool_name=plan.tool_name or "system",
                action_type=plan.action_type.value,
                success=True,
                status=ToolActionStatus.SUCCESS,
                output={"action": plan.action_type.value, "reason": plan.reason},
            )

        tool_name = plan.tool_name or "unknown"
        self.validate_action(plan, context)

        adapter = self._resolve_tool(tool_name)

        # Check circuit breaker if configured
        breaker: CircuitBreaker | None = None
        if self._circuit_breakers and tool_name in self._circuit_breakers:
            breaker = self._circuit_breakers[tool_name]
        elif self._circuit_breaker_registry:
            breaker = self._circuit_breaker_registry.get_breaker(tool_name)

        if breaker and not breaker.allow_request():
            cooldown = breaker.cooldown_remaining() if callable(getattr(breaker, "cooldown_remaining", None)) else breaker.cooldown_remaining
            logger.warning(
                "Tool execution rejected: circuit breaker '%s' is OPEN (cooldown %.1fs remaining)",
                tool_name,
                cooldown,
            )
            return ToolResult(
                tool_name=tool_name,
                action_type=plan.action_parameters.get("action_type", tool_name),
                success=False,
                status=ToolActionStatus.TOOL_UNAVAILABLE,
                recoverable=True,
                error_message=(
                    f"Tool '{tool_name}' is temporarily unavailable: "
                    f"Circuit breaker is OPEN ({cooldown:.1f}s cooldown remaining)"
                ),
                duration_seconds=0.0,
                metadata={"circuit_state": "open", "breaker_name": tool_name},
            )

        # Check availability if tool provides metadata
        if hasattr(adapter, "get_metadata"):
            try:
                meta = adapter.get_metadata()
                if hasattr(meta, "is_available") and not meta.is_available:
                    return ToolResult(
                        tool_name=tool_name,
                        action_type=plan.action_parameters.get("action_type", tool_name),
                        success=False,
                        status=ToolActionStatus.TOOL_UNAVAILABLE,
                        error_message=f"Tool '{tool_name}' is currently unavailable",
                        duration_seconds=0.0,
                    )
            except Exception as exc:
                logger.warning("Error checking metadata for tool '%s': %s", tool_name, exc)

        action = self._build_tool_action(plan)
        idempotent = is_action_idempotent(action.action_type)

        attempt = 1
        max_attempts = self._recovery_policy.max_attempts if self._recovery_policy else 1
        elapsed_retry_time = 0.0

        while attempt <= max_attempts:
            start_time = time.monotonic()
            try:
                result: ToolExecutionResult = await asyncio.wait_for(
                    adapter.execute(action),
                    timeout=action.timeout_seconds,
                )
                duration = time.monotonic() - start_time

                requires_human = (result.status == ToolActionStatus.HUMAN_INTERVENTION_REQUIRED)
                recoverable = (result.status in (
                    ToolActionStatus.RECOVERABLE_FAILURE,
                    ToolActionStatus.TIMEOUT,
                ))

                if result.status == ToolActionStatus.SUCCESS:
                    if breaker:
                        breaker.record_success()
                    return ToolResult(
                        tool_name=tool_name,
                        action_type=action.action_type,
                        success=True,
                        status=result.status,
                        requires_human=False,
                        recoverable=False,
                        output=result.output,
                        error_message=result.error_message,
                        duration_seconds=duration,
                        metadata=result.metadata,
                    )

                # Action returned non-success status
                if breaker and not requires_human:
                    breaker.record_failure()

                if requires_human:
                    return ToolResult(
                        tool_name=tool_name,
                        action_type=action.action_type,
                        success=False,
                        status=result.status,
                        requires_human=True,
                        recoverable=False,
                        output=result.output,
                        error_message=result.error_message,
                        duration_seconds=duration,
                        metadata=result.metadata,
                    )

                # Recoverable check with RecoveryPolicy
                if recoverable and idempotent and self._recovery_policy and attempt < max_attempts and not context.cancelled:
                    classified = classify_exception(
                        Exception(result.error_message or "Recoverable tool failure"),
                        action_type=action.action_type,
                        is_idempotent=True,
                    )
                    decision = self._recovery_policy.evaluate(
                        classified,
                        attempt=attempt,
                        elapsed_retry_time=elapsed_retry_time,
                        is_idempotent=True,
                        is_cancelled=context.cancelled,
                    )
                    if decision.action == RecoveryAction.RETRY:
                        logger.info(
                            "Tool '%s' recoverable failure (attempt %d/%d). Retrying after %.2fs backoff",
                            tool_name, attempt, max_attempts, decision.backoff_seconds,
                        )
                        await self._recovery_policy.sleeper.sleep(decision.backoff_seconds)
                        elapsed_retry_time += decision.backoff_seconds
                        attempt += 1
                        continue

                return ToolResult(
                    tool_name=tool_name,
                    action_type=action.action_type,
                    success=False,
                    status=result.status,
                    requires_human=requires_human,
                    recoverable=recoverable,
                    output=result.output,
                    error_message=result.error_message,
                    duration_seconds=duration,
                    metadata=result.metadata,
                )

            except asyncio.TimeoutError:
                duration = time.monotonic() - start_time
                logger.warning("Tool '%s' timed out after %.1fs", tool_name, duration)
                if breaker:
                    breaker.record_failure()

                # Unknown outcome on non-idempotent action
                if not idempotent:
                    logger.warning(
                        "Timeout on non-idempotent action '%s' for tool '%s'. "
                        "Outcome is UNCERTAIN — repetition prohibited; requiring human intervention.",
                        action.action_type, tool_name,
                    )
                    return ToolResult(
                        tool_name=tool_name,
                        action_type=action.action_type,
                        success=False,
                        status=ToolActionStatus.TIMEOUT,
                        requires_human=True,
                        recoverable=False,
                        error_message=(
                            f"Tool '{tool_name}' timed out after {action.timeout_seconds:.1f}s on non-idempotent action '{action.action_type}'. "
                            f"Outcome is uncertain; repetition prohibited."
                        ),
                        duration_seconds=duration,
                    )

                # Idempotent timeout: eligible for retry
                if self._recovery_policy and attempt < max_attempts and not context.cancelled:
                    classified = OperationTimeoutError(f"Tool timed out after {action.timeout_seconds:.1f}s")
                    decision = self._recovery_policy.evaluate(
                        classified,
                        attempt=attempt,
                        elapsed_retry_time=elapsed_retry_time,
                        is_idempotent=True,
                        is_cancelled=context.cancelled,
                    )
                    if decision.action == RecoveryAction.RETRY:
                        logger.info(
                            "Tool '%s' timeout (attempt %d/%d). Retrying after %.2fs backoff",
                            tool_name, attempt, max_attempts, decision.backoff_seconds,
                        )
                        await self._recovery_policy.sleeper.sleep(decision.backoff_seconds)
                        elapsed_retry_time += decision.backoff_seconds
                        attempt += 1
                        continue

                return ToolResult(
                    tool_name=tool_name,
                    action_type=action.action_type,
                    success=False,
                    status=ToolActionStatus.TIMEOUT,
                    recoverable=True,
                    error_message=f"Tool timed out after {action.timeout_seconds:.1f}s",
                    duration_seconds=duration,
                )

            except Exception as exc:
                duration = time.monotonic() - start_time
                logger.exception("Tool '%s' raised an unexpected error", tool_name)
                if breaker:
                    breaker.record_failure(exc)

                classified = classify_exception(exc, action_type=action.action_type, is_idempotent=idempotent)
                status = (
                    ToolActionStatus.HUMAN_INTERVENTION_REQUIRED
                    if classified.requires_human
                    else (
                        ToolActionStatus.RECOVERABLE_FAILURE
                        if classified.recoverable
                        else ToolActionStatus.NON_RECOVERABLE_FAILURE
                    )
                )
                return ToolResult(
                    tool_name=tool_name,
                    action_type=action.action_type,
                    success=False,
                    status=status,
                    requires_human=classified.requires_human,
                    recoverable=classified.recoverable,
                    error_message=f"Tool error: {classified.message}",
                    duration_seconds=duration,
                )

