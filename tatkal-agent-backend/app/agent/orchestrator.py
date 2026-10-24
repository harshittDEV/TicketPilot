"""
Generic agent orchestrator.

Coordinates the sense-plan-act-verify loop using typed interfaces.
Does NOT implement browser, booking, or train-comparison behaviour.

The orchestrator's conceptual loop:
    1. Load task and run, verify states permit execution.
    2. Build execution context.
    3. Obtain an observation.
    4. Ask the planner for the next action.
    5. Validate the proposed action.
    6. Resolve and execute the tool.
    7. Obtain a fresh observation.
    8. Verify the result.
    9. Persist run progress.
    10. Repeat until completion, pause, cancellation, or terminal error.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.agent.errors import (
    ActionLimitExceededError,
    OrchestrationError,
    PlannerError,
    RunCancelledError,
    RunDeadlineExceededError,
    VerificationFailedError,
)
from app.agent.llm.base import BaseLLMClient, LLMRequest
from app.agent.models import (
    ActionType,
    ExecutionContext,
    Observation,
    PlannerRequest,
    PlannerResponse,
    StepRecord,
    ToolResult,
)
from app.agent.observer import BaseObserver
from app.agent.tool_executor import ToolExecutor
from app.agent.verifier import BaseVerifier
from app.integrations.contracts import ToolActionStatus
from app.services.run_state_machine import RunStatus

logger = logging.getLogger(__name__)


class OrchestratorResult:
    """Result returned by the orchestrator after a run attempt."""

    def __init__(
        self,
        *,
        run_id: str,
        final_status: str,
        steps_completed: int,
        step_records: list[StepRecord],
        error_message: Optional[str] = None,
    ) -> None:
        self.run_id = run_id
        self.final_status = final_status
        self.steps_completed = steps_completed
        self.step_records = step_records
        self.error_message = error_message

    def __repr__(self) -> str:
        return (
            f"<OrchestratorResult run={self.run_id!r} "
            f"status={self.final_status!r} steps={self.steps_completed}>"
        )


class Orchestrator:
    """
    Generic agent orchestrator.

    Coordinates planner, tool executor, observer, and verifier through
    small, typed methods.  Never directly implements task-specific
    behaviour.
    """

    def __init__(
        self,
        *,
        planner: BaseLLMClient,
        tool_executor: ToolExecutor,
        observer: BaseObserver,
        verifier: BaseVerifier,
        max_steps: int = 100,
        max_run_duration_seconds: float = 3600.0,
        max_action_timeout_seconds: float = 30.0,
    ) -> None:
        self._planner = planner
        self._tool_executor = tool_executor
        self._observer = observer
        self._verifier = verifier
        self._max_steps = max_steps
        self._max_run_duration = max_run_duration_seconds
        self._max_action_timeout = max_action_timeout_seconds

    # ── Public entry point ───────────────────────────────────────

    async def execute(
        self,
        *,
        task_id: str,
        run_id: str,
        task_type: str,
        task_configuration: dict,
        initial_step: int = 0,
        on_step_complete: Optional[callable] = None,
    ) -> OrchestratorResult:
        """
        Execute the sense-plan-act-verify loop.

        This method does NOT persist state itself — the caller
        (RunService / API) is responsible for creating the run,
        transitioning it to RUNNING, and finalising it.

        Args:
            task_id: The task being executed.
            run_id: The execution run ID.
            task_type: Task type identifier.
            task_configuration: Non-sensitive task config.
            initial_step: Step number to resume from (e.g. after WAITING_FOR_HUMAN).
            on_step_complete: Optional callback invoked after each step.

        Returns:
            OrchestratorResult with the outcome.
        """
        context = self._build_context(
            task_id=task_id,
            run_id=run_id,
            task_type=task_type,
            task_configuration=task_configuration,
            initial_step=initial_step,
        )

        step_records: list[StepRecord] = []
        error_message: str | None = None
        final_status: str | None = None

        try:
            # Initial observation
            observation = await self._observer.observe(context)

            while context.is_within_limits() and not context.cancelled:
                step_start = time.monotonic()

                # 1. Plan
                plan = await self._get_plan(context, observation)

                # 2. Check for terminal plan actions
                if plan.action_type == ActionType.COMPLETE:
                    record = StepRecord(
                        step_number=context.current_step,
                        action_type=plan.action_type.value,
                        reason=plan.reason,
                    )
                    step_records.append(record)
                    final_status = RunStatus.COMPLETED.value
                    break

                if plan.action_type == ActionType.FAIL:
                    record = StepRecord(
                        step_number=context.current_step,
                        action_type=plan.action_type.value,
                        reason=plan.reason,
                    )
                    step_records.append(record)
                    final_status = RunStatus.FAILED.value
                    error_message = plan.reason or "Planner declared failure"
                    break

                if plan.action_type == ActionType.WAIT_FOR_HUMAN:
                    record = StepRecord(
                        step_number=context.current_step,
                        action_type=plan.action_type.value,
                        reason=plan.reason,
                    )
                    step_records.append(record)
                    final_status = RunStatus.WAITING_FOR_HUMAN.value
                    error_message = plan.reason or "Human intervention required"
                    from app.services.audit_service import get_audit_service
                    get_audit_service().record_human_intervention(
                        task_id=context.task_id,
                        run_id=context.run_id,
                        reason=error_message,
                        context={"step": context.current_step},
                    )
                    context.action_count += 1
                    break

                # 3. Validate action
                self._tool_executor.validate_action(plan, context)

                # 4. Get pre-action observation ID
                observation_before_id = observation.observation_id

                # 5. Execute
                tool_result = await self._tool_executor.execute(plan, context)

                # 6. Post-action observation
                observation_after = await self._observer.observe(context)

                # 7. Verify
                verification = await self._verifier.verify(
                    action=plan,
                    tool_result=tool_result,
                    observation_before=observation,
                    observation_after=observation_after,
                    expected_result=plan.expected_result,
                )

                # 8. Record step
                step_duration = time.monotonic() - step_start
                record = StepRecord(
                    step_number=context.current_step,
                    action_type=plan.action_type.value,
                    tool_name=plan.tool_name,
                    parameters=plan.action_parameters,
                    reason=plan.reason,
                    tool_result=tool_result,
                    observation_before=observation_before_id,
                    observation_after=observation_after.observation_id,
                    verification=verification,
                    duration_seconds=step_duration,
                )
                step_records.append(record)

                try:
                    from app.services.audit_service import get_audit_service
                    tool_outcome = "SUCCESS" if getattr(tool_result, "success", True) else "FAILURE"
                    art_ref = getattr(tool_result, "artifact_ref", None)
                    if not art_ref and hasattr(tool_result, "metadata") and isinstance(tool_result.metadata, dict):
                        art_ref = tool_result.metadata.get("artifact_ref")
                    get_audit_service().record_tool_execution(
                        run_id=context.run_id,
                        task_id=context.task_id,
                        tool_name=plan.tool_name or "unknown",
                        action_type=plan.action_type.value,
                        outcome=tool_outcome,
                        parameters=plan.action_parameters,
                        result_status=getattr(tool_result.status, "value", str(tool_result.status)),
                        duration_seconds=step_duration,
                        error_code=getattr(tool_result, "error_code", None),
                        evidence_references=[art_ref] if art_ref else None,
                    )
                except Exception as audit_err:
                    logger.debug("Non-critical tool audit recording failed: %s", audit_err)

                # 9. Handle human intervention
                if tool_result.requires_human or tool_result.status == ToolActionStatus.HUMAN_INTERVENTION_REQUIRED:
                    final_status = RunStatus.WAITING_FOR_HUMAN.value
                    error_message = tool_result.error_message or "Human intervention required"
                    get_audit_service().record_human_intervention(
                        task_id=context.task_id,
                        run_id=context.run_id,
                        reason=error_message,
                        context={"step": context.current_step, "tool_name": plan.tool_name},
                    )
                    if on_step_complete:
                        on_step_complete(context, record)
                    break

                # 10. Handle verification failure
                if not verification.success:
                    final_status = RunStatus.FAILED.value
                    error_message = (
                        f"Verification failed at step {context.current_step}: "
                        f"{verification.explanation}"
                    )
                    get_audit_service().record_event(
                        event_type="verification.failed",
                        event_category="RUN",
                        outcome="FAILURE",
                        source="orchestrator",
                        task_id=context.task_id,
                        run_id=context.run_id,
                        error_code="VERIFICATION_FAILED",
                        metadata={"step": context.current_step, "explanation": verification.explanation},
                    )
                    if on_step_complete:
                        on_step_complete(context, record)
                    break

                # 10. Update context
                context.current_step += 1
                context.action_count += 1
                observation = observation_after

                # 11. Callback
                if on_step_complete:
                    on_step_complete(context, record)

            # Check why we exited if not already set by explicit action
            if context.cancelled:
                final_status = RunStatus.CANCELLED.value
                error_message = "Run cancelled by external request"
            elif final_status is None:
                if not context.is_within_limits():
                    if context.action_count >= context.max_steps:
                        final_status = RunStatus.FAILED.value
                        error_message = f"Action limit exceeded ({context.max_steps} steps)"
                    else:
                        final_status = RunStatus.FAILED.value
                        error_message = "Run deadline exceeded"
                else:
                    final_status = RunStatus.COMPLETED.value

        except RunCancelledError:
            final_status = RunStatus.CANCELLED.value
            error_message = "Run cancelled"
        except ActionLimitExceededError as exc:
            final_status = RunStatus.FAILED.value
            error_message = str(exc)
        except RunDeadlineExceededError as exc:
            final_status = RunStatus.FAILED.value
            error_message = str(exc)
        except PlannerError as exc:
            final_status = RunStatus.FAILED.value
            error_message = f"Planner error: {exc.message}"
        except OrchestrationError as exc:
            final_status = RunStatus.FAILED.value
            error_message = f"Orchestration error: {exc.message}"
        except Exception as exc:
            logger.exception("Unhandled orchestrator error")
            final_status = RunStatus.FAILED.value
            error_message = f"Unexpected error: {exc!s}"

        return OrchestratorResult(
            run_id=run_id,
            final_status=final_status,
            steps_completed=context.action_count,
            step_records=step_records,
            error_message=error_message,
        )

    # ── Private helpers ──────────────────────────────────────────

    def _build_context(
        self,
        *,
        task_id: str,
        run_id: str,
        task_type: str,
        task_configuration: dict,
        initial_step: int = 0,
    ) -> ExecutionContext:
        """Build the initial execution context for a run."""
        deadline = datetime.now(timezone.utc) + timedelta(
            seconds=self._max_run_duration
        )
        return ExecutionContext(
            task_id=task_id,
            run_id=run_id,
            task_type=task_type,
            task_configuration=task_configuration,
            run_status=RunStatus.RUNNING.value,
            current_step=initial_step,
            action_count=initial_step,
            max_steps=self._max_steps,
            max_run_duration_seconds=self._max_run_duration,
            max_action_timeout_seconds=self._max_action_timeout,
            run_deadline=deadline,
        )

    async def _get_plan(
        self,
        context: ExecutionContext,
        observation: Observation,
    ) -> PlannerResponse:
        """
        Ask the planner for the next action.

        Validates the response structure before returning.
        """
        planner_request = PlannerRequest(
            task_type=context.task_type,
            task_configuration=context.task_configuration,
            current_step=context.current_step,
            max_steps=context.max_steps,
            observation=observation.content,
            available_tools=self._tool_executor._registry.registered_names(),
            previous_actions=[],  # Could be populated from step_records
        )

        llm_request = LLMRequest(
            planner_request=planner_request,
            timeout_seconds=context.max_action_timeout_seconds,
        )

        try:
            llm_response = await self._planner.plan(llm_request)
        except PlannerError:
            raise
        except Exception as exc:
            raise PlannerError(f"Failed to get plan: {exc!s}")

        plan = llm_response.planner_response

        # Validate: TOOL_ACTION requires tool_name
        if plan.action_type == ActionType.TOOL_ACTION and not plan.tool_name:
            raise PlannerError(
                "Planner returned TOOL_ACTION without specifying tool_name"
            )

        return plan


# Alias for backward/forward naming compatibility
AgentOrchestrator = Orchestrator
