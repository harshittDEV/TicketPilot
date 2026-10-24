"""
Run service — business logic for execution-run lifecycle management.

Owns:
    - Run creation with single-active-run enforcement.
    - Run retrieval and listing.
    - State transitions via the centralised run state machine.
    - Pause, resume, and cancellation coordination.
    - Optimistic concurrency control.

Does NOT own:
    - Task state transitions (delegates to TaskService).
    - Agent orchestration logic.
    - Scheduling.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.execution_run import ExecutionRun
from app.schemas.run import RunListMeta
from app.services.run_repository import RunRepository
from app.services.run_state_machine import (
    ACTIVE_RUN_STATES,
    CANCELLABLE_RUN_STATES,
    PAUSABLE_RUN_STATES,
    TERMINAL_RUN_STATES,
    RunStatus,
    RunNotFoundError,
    RunStateConflictError,
    RunValidationError,
    DuplicateActiveRunError,
    InvalidRunTransitionError,
    validate_run_transition,
)
from app.services.task_state_machine import (
    TaskStatus,
    TERMINAL_STATES as TERMINAL_TASK_STATES,
    TaskNotFoundError,
)
from app.models.task import Task

logger = logging.getLogger(__name__)


class RunService:
    """High-level execution-run lifecycle operations."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = RunRepository(db)

    # ── Create ───────────────────────────────────────────────────

    def create_run(self, task_id: str) -> ExecutionRun:
        """
        Create a new execution run for a task.

        Validates:
            - The task exists.
            - The task is not in a terminal state.
            - No other active run exists for the task.
        """
        # Verify task exists
        task = self._db.get(Task, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        # Reject if task is in a terminal state
        try:
            task_status = TaskStatus(task.status)
        except ValueError:
            raise RunValidationError(
                f"Task '{task_id}' has an unrecognised status: '{task.status}'"
            )

        if task_status in TERMINAL_TASK_STATES:
            raise RunValidationError(
                f"Cannot create a run for task '{task_id}' "
                f"in terminal state '{task.status}'."
            )

        # Enforce single-active-run policy
        existing = self._repo.get_active_run_for_task(task_id)
        if existing is not None:
            raise DuplicateActiveRunError(task_id, existing.id)

        run = ExecutionRun(
            task_id=task_id,
            status=RunStatus.PENDING.value,
        )
        run = self._repo.create(run)
        self._repo.commit()

        logger.info(
            "Run created: id=%s task=%s status=%s",
            run.id, run.task_id, run.status,
        )

        from app.services.audit_service import get_audit_service
        get_audit_service().record_run_lifecycle(
            run_id=run.id,
            task_id=run.task_id,
            event_type="run.created",
            outcome="SUCCESS",
            to_status=run.status,
            db=self._db,
        )
        return run

    # ── Read ─────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> ExecutionRun:
        """Retrieve a run by ID or raise RunNotFoundError."""
        run = self._repo.get_by_id(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    def get_active_run(self, task_id: str) -> ExecutionRun | None:
        """Return the currently active run for a task, or None."""
        return self._repo.get_active_run_for_task(task_id)

    def list_runs(
        self,
        task_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionRun], RunListMeta]:
        """Return paginated runs for a task."""
        # Verify task exists
        task = self._db.get(Task, task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        runs, total = self._repo.list_runs_for_task(
            task_id, page=page, page_size=page_size,
        )
        total_pages = max(1, math.ceil(total / page_size))
        meta = RunListMeta(
            total=total, page=page, page_size=page_size, total_pages=total_pages,
        )
        return runs, meta

    # ── State transitions ────────────────────────────────────────

    def transition_run(
        self,
        run_id: str,
        target_status_str: str,
        *,
        expected_version: int | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
        current_step: str | None = None,
        steps_completed: int | None = None,
    ) -> ExecutionRun:
        """
        Transition a run to a new state via the centralised run state machine.

        Args:
            run_id: The run to transition.
            target_status_str: Target state (must be a valid RunStatus value).
            expected_version: For optimistic concurrency control.
            error_code: Machine-readable error code (for FAILED transitions).
            error_summary: Human-readable error summary (for FAILED transitions).
            current_step: Update the current step identifier.
            steps_completed: Update the step counter.

        Raises:
            RunNotFoundError: If the run does not exist.
            RunValidationError: If the target status is invalid.
            InvalidRunTransitionError: If the transition is not allowed.
            RunStateConflictError: If the version does not match.
        """
        # Parse target status
        try:
            target_status = RunStatus(target_status_str)
        except ValueError:
            raise RunValidationError(
                f"Invalid target run status: '{target_status_str}'. "
                f"Allowed values: {[s.value for s in RunStatus]}"
            )

        run = self.get_run(run_id)
        current_status = RunStatus(run.status)

        # Optimistic concurrency check
        if expected_version is not None and run.version != expected_version:
            raise RunStateConflictError(run_id)

        # Validate transition
        validate_run_transition(current_status, target_status)

        # Apply state change
        now = datetime.now(timezone.utc)
        run.status = target_status.value
        run.version += 1

        # Apply lifecycle timestamps
        if target_status == RunStatus.RUNNING and run.started_at is None:
            run.started_at = now
        if target_status in TERMINAL_RUN_STATES:
            run.ended_at = now

        # Apply error info or intervention reason
        if error_code is not None:
            run.error_code = error_code
        if error_summary is not None:
            run.error_summary = error_summary

        # Apply optional step updates
        if current_step is not None:
            run.current_step = current_step
        if steps_completed is not None:
            run.steps_completed = steps_completed

        run = self._repo.update(run)
        self._repo.commit()

        logger.info(
            "Run transitioned: id=%s %s → %s (v%d)",
            run.id, current_status.value, target_status.value, run.version,
        )

        from app.services.audit_service import get_audit_service
        run_outcome = (
            "FAILURE" if target_status == RunStatus.FAILED
            else ("PENDING" if target_status == RunStatus.WAITING_FOR_HUMAN else "SUCCESS")
        )
        get_audit_service().record_run_lifecycle(
            run_id=run.id,
            task_id=run.task_id,
            event_type=f"run.{target_status.value.lower()}",
            outcome=run_outcome,
            from_status=current_status.value,
            to_status=target_status.value,
            error_code=error_code,
            metadata={
                "error_summary": error_summary,
                "current_step": run.current_step,
                "steps_completed": run.steps_completed,
            },
            db=self._db,
        )
        return run

    # ── Pause ────────────────────────────────────────────────────

    def pause_run(self, run_id: str) -> ExecutionRun:
        """Pause a running execution run."""
        run = self.get_run(run_id)
        current_status = RunStatus(run.status)

        if current_status not in PAUSABLE_RUN_STATES:
            raise InvalidRunTransitionError(
                current_status.value, RunStatus.PAUSED.value,
            )

        return self.transition_run(run_id, RunStatus.PAUSED.value)

    # ── Resume ───────────────────────────────────────────────────

    def resume_run(self, run_id: str) -> ExecutionRun:
        """Resume a paused or waiting-for-human run."""
        run = self.get_run(run_id)
        current_status = RunStatus(run.status)

        if current_status not in {RunStatus.PAUSED, RunStatus.WAITING_FOR_HUMAN}:
            raise InvalidRunTransitionError(
                current_status.value, RunStatus.RUNNING.value,
            )

        return self.transition_run(run_id, RunStatus.RUNNING.value)

    # ── Cancel ───────────────────────────────────────────────────

    def cancel_run(self, run_id: str) -> ExecutionRun:
        """
        Cancel a run if its current state permits cancellation.

        Already-cancelled runs return the existing state without error.
        """
        run = self.get_run(run_id)
        current_status = RunStatus(run.status)

        # Idempotent
        if current_status == RunStatus.CANCELLED:
            return run

        if current_status in TERMINAL_RUN_STATES:
            raise InvalidRunTransitionError(
                current_status.value, RunStatus.CANCELLED.value,
            )

        if current_status not in CANCELLABLE_RUN_STATES:
            raise InvalidRunTransitionError(
                current_status.value, RunStatus.CANCELLED.value,
            )

        return self.transition_run(run_id, RunStatus.CANCELLED.value)

    # ── Execute ──────────────────────────────────────────────────

    async def execute_run(
        self,
        run_id: str,
        *,
        planner: Any | None = None,
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ExecutionRun:
        """
        Execute an execution run through the generic agent orchestrator.

        Coordinates:
            - Validates run and task state.
            - Prevents re-execution of completed, cancelled, or failed runs.
            - Transitions task and run to RUNNING.
            - Resolves orchestrator dependencies (planner, tools, observer, verifier).
            - Executes sense-plan-act-verify loop.
            - Finalizes run and task to terminal states (COMPLETED, FAILED, WAITING_FOR_HUMAN).
            - Records audit trail and execution summary evidence.
        """
        import json
        from app.agent.llm.base import FakePlanner
        from app.agent.models import ActionType, PlannerResponse
        from app.agent.observer import DefaultObserver
        from app.agent.orchestrator import Orchestrator
        from app.agent.tool_executor import ToolExecutor
        from app.agent.verifier import DeterministicVerifier
        from app.core.config import get_settings
        from app.services.task_service import TaskService

        run = self.get_run(run_id)
        current_status = RunStatus(run.status)

        if current_status in TERMINAL_RUN_STATES:
            raise InvalidRunTransitionError(
                current_status.value,
                RunStatus.RUNNING.value,
            )

        task = self._db.get(Task, run.task_id)
        if task is None:
            raise TaskNotFoundError(run.task_id)

        task_svc = TaskService(self._db)

        # Transition task to RUNNING if not already
        if task.status == TaskStatus.CREATED.value:
            task_svc.transition_task(task.id, TaskStatus.READY.value)
            task_svc.transition_task(task.id, TaskStatus.RUNNING.value)
        elif task.status in (
            TaskStatus.READY.value,
            TaskStatus.AWAITING_HUMAN.value,
            TaskStatus.AWAITING_PAYMENT_APPROVAL.value,
        ):
            task_svc.transition_task(task.id, TaskStatus.RUNNING.value)

        # Transition run to RUNNING
        if current_status in {RunStatus.PENDING, RunStatus.PAUSED}:
            run = self.transition_run(run.id, RunStatus.RUNNING.value)

        settings = get_settings()

        # Resolve planner (uses TatkalBookingAgentPlanner when autonomous_agent is requested)
        if planner is None:
            cfg = task.configuration or {}
            is_autonomous = (
                task.task_type in ("autonomous_booking", "tatkal_agent")
                or cfg.get("autonomous_agent") is True
                or cfg.get("agent_mode") == "autonomous"
            )
            if is_autonomous:
                from app.agent.booking_planner import TatkalBookingAgentPlanner
                planner = TatkalBookingAgentPlanner()
            else:
                planner = FakePlanner([
                    PlannerResponse(
                        action_type=ActionType.COMPLETE,
                        reason="Task execution completed successfully",
                        task_complete=True,
                    )
                ])

        from app.integrations.registry import get_registry
        registry = get_registry()
        allocated_max_steps = (run.steps_completed or 0) + (max_steps or 100)
        orchestrator = Orchestrator(
            planner=planner,
            tool_executor=ToolExecutor(registry),
            observer=DefaultObserver(registry),
            verifier=DeterministicVerifier(),
            max_steps=allocated_max_steps,
            max_run_duration_seconds=timeout_seconds or 3600.0,
        )

        logger.info("Executing orchestrator loop for run '%s' (task '%s')", run.id, task.id)
        result = await orchestrator.execute(
            task_id=task.id,
            run_id=run.id,
            task_type=task.task_type,
            task_configuration=task.configuration or {},
            initial_step=run.steps_completed,
        )

        # Synchronize outcomes
        if result.final_status == RunStatus.COMPLETED.value:
            run = self.transition_run(
                run.id,
                RunStatus.COMPLETED.value,
                steps_completed=result.steps_completed,
            )
            if task.status != TaskStatus.COMPLETED.value:
                task_svc.transition_task(task.id, TaskStatus.COMPLETED.value)

            # Capture structured execution summary as evidence
            if settings.audit_enabled:
                try:
                    from app.services.evidence_service import get_evidence_service
                    summary_data = {
                        "task_id": task.id,
                        "run_id": run.id,
                        "final_status": result.final_status,
                        "steps_completed": result.steps_completed,
                        "step_records": [
                            s.model_dump() if hasattr(s, "model_dump") else s.__dict__
                            for s in result.step_records
                        ],
                    }
                    get_evidence_service().capture_evidence(
                        self._db,
                        data=json.dumps(summary_data, default=str).encode("utf-8"),
                        evidence_type="EXECUTION_SUMMARY",
                        task_id=task.id,
                        run_id=run.id,
                        content_type="application/json",
                        capture_source="orchestrator",
                        metadata={"steps_completed": result.steps_completed},
                    )
                except Exception as exc:
                    logger.warning("Failed to store execution summary evidence: %s", exc)

        elif result.final_status == RunStatus.WAITING_FOR_HUMAN.value:
            run = self.transition_run(
                run.id,
                RunStatus.WAITING_FOR_HUMAN.value,
                steps_completed=result.steps_completed,
                error_summary=result.error_message,
            )
            is_payment_boundary = bool(
                result.error_message and "PAYMENT_STAGE_REACHED" in result.error_message
            )
            target_task_status = (
                TaskStatus.AWAITING_PAYMENT_APPROVAL.value
                if is_payment_boundary
                else TaskStatus.AWAITING_HUMAN.value
            )
            if task.status != target_task_status:
                task_svc.transition_task(task.id, target_task_status)

            if is_payment_boundary:
                from app.services.audit_service import get_audit_service
                get_audit_service().record_event(
                    event_type="booking.payment_boundary_reached",
                    event_category="RUN",
                    outcome="SUCCESS",
                    source="orchestrator",
                    task_id=task.id,
                    run_id=run.id,
                    metadata={
                        "step": result.steps_completed,
                        "notice": "Automated execution stopped at payment boundary. Human authorization required.",
                    },
                    db=self._db,
                )

        elif result.final_status == RunStatus.FAILED.value:
            run = self.transition_run(
                run.id,
                RunStatus.FAILED.value,
                steps_completed=result.steps_completed,
                error_summary=result.error_message,
            )
            if task.status != TaskStatus.FAILED.value:
                task_svc.transition_task(
                    task.id,
                    TaskStatus.FAILED.value,
                    error_summary=result.error_message,
                )

        elif result.final_status == RunStatus.CANCELLED.value:
            run = self.transition_run(
                run.id,
                RunStatus.CANCELLED.value,
                steps_completed=result.steps_completed,
            )
            if task.status != TaskStatus.CANCELLED.value:
                task_svc.transition_task(task.id, TaskStatus.CANCELLED.value)

        return self.get_run(run.id)
