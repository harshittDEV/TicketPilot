"""
Task service — business logic for task lifecycle management.

Owns:
    - Task creation with validated defaults.
    - Task retrieval and listing.
    - Metadata updates (name, description, configuration only).
    - State transitions via the centralised state machine.
    - Cancellation enforcement.
    - Optimistic concurrency control.

Does NOT own:
    - Task execution / agent orchestration.
    - Scheduling.
    - Booking or comparison logic.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.task import Task
from app.schemas.task import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskListMeta,
)
from app.services.task_repository import TaskRepository
from app.services.task_state_machine import (
    CANCELLABLE_STATES,
    TERMINAL_STATES,
    TaskStatus,
    TaskNotFoundError,
    TaskStateConflictError,
    TaskValidationError,
    InvalidTaskTransitionError,
    validate_transition,
)

logger = logging.getLogger(__name__)


class TaskService:
    """High-level task lifecycle operations."""

    def __init__(self, db: Session) -> None:
        self._repo = TaskRepository(db)

    # ── Create ───────────────────────────────────────────────────

    def create_task(self, request: TaskCreateRequest) -> Task:
        """
        Create a new task in the CREATED state.

        The server generates the ID, timestamps, and initial version.
        """
        task = Task(
            name=request.name,
            task_type=request.task_type,
            description=request.description,
            configuration=request.configuration or {},
            status=TaskStatus.CREATED.value,
        )
        task = self._repo.create(task)
        self._repo.commit()
        logger.info("Task created: id=%s type=%s", task.id, task.task_type)

        from app.services.audit_service import get_audit_service
        get_audit_service().record_task_lifecycle(
            task_id=task.id,
            event_type="task.created",
            outcome="SUCCESS",
            to_status=task.status,
            metadata={"task_type": task.task_type, "name": task.name},
            db=self._repo._db,
        )
        return task

    # ── Read ─────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Task:
        """Retrieve a task by ID or raise TaskNotFoundError."""
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def list_tasks(
        self,
        *,
        status: str | None = None,
        task_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Task], TaskListMeta]:
        """
        Return a paginated, filtered list of tasks.

        Validates pagination parameters and returns metadata.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 100))  # cap at 100

        # Validate status filter if provided
        if status:
            try:
                TaskStatus(status)
            except ValueError:
                raise TaskValidationError(
                    f"Invalid status filter: '{status}'. "
                    f"Allowed values: {[s.value for s in TaskStatus]}"
                )

        tasks, total = self._repo.list_tasks(
            status=status, task_type=task_type, page=page, page_size=page_size
        )

        total_pages = max(1, math.ceil(total / page_size))
        meta = TaskListMeta(
            total=total, page=page, page_size=page_size, total_pages=total_pages
        )
        return tasks, meta

    # ── Update metadata ──────────────────────────────────────────

    def update_task(self, task_id: str, request: TaskUpdateRequest) -> Task:
        """
        Update permitted metadata fields on a task.

        Only name, description, and configuration can be changed.
        Status, timestamps, version, and ID are never changed here.
        """
        task = self.get_task(task_id)

        if task.status in {s.value for s in TERMINAL_STATES}:
            raise InvalidTaskTransitionError(
                task.status, f"metadata update (task is in terminal state {task.status})"
            )

        if request.name is not None:
            task.name = request.name
        if request.description is not None:
            task.description = request.description
        if request.configuration is not None:
            task.configuration = request.configuration

        task = self._repo.update(task)
        self._repo.commit()
        logger.info("Task metadata updated: id=%s", task.id)

        from app.services.audit_service import get_audit_service
        get_audit_service().record_task_lifecycle(
            task_id=task.id,
            event_type="task.metadata_updated",
            outcome="SUCCESS",
            to_status=task.status,
            db=self._repo._db,
        )
        return task

    # ── State transitions ────────────────────────────────────────

    def transition_task(
        self,
        task_id: str,
        target_status_str: str,
        *,
        expected_version: int | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> Task:
        """
        Transition a task to a new state via the centralised state machine.

        Args:
            task_id: The task to transition.
            target_status_str: The target state (must be a valid TaskStatus value).
            expected_version: If provided, used for optimistic concurrency control.
            error_code: Machine-readable error code (for FAILED transitions).
            error_summary: Human-readable error summary (for FAILED transitions).

        Raises:
            TaskNotFoundError: If the task does not exist.
            TaskValidationError: If the target status is invalid.
            InvalidTaskTransitionError: If the transition is not allowed.
            TaskStateConflictError: If the version does not match (stale update).
        """
        # Parse target status
        try:
            target_status = TaskStatus(target_status_str)
        except ValueError:
            raise TaskValidationError(
                f"Invalid target status: '{target_status_str}'. "
                f"Allowed values: {[s.value for s in TaskStatus]}"
            )

        task = self.get_task(task_id)
        current_status = TaskStatus(task.status)

        # Optimistic concurrency check
        if expected_version is not None and task.version != expected_version:
            raise TaskStateConflictError(task_id)

        # Validate transition through centralised state machine
        validate_transition(current_status, target_status)

        # Apply state change
        now = datetime.now(timezone.utc)
        task.status = target_status.value
        task.version += 1

        # Apply lifecycle timestamps
        if target_status == TaskStatus.RUNNING and task.started_at is None:
            task.started_at = now
        elif target_status == TaskStatus.COMPLETED:
            task.completed_at = now
        elif target_status == TaskStatus.CANCELLED:
            task.cancelled_at = now
        elif target_status == TaskStatus.FAILED:
            task.error_code = error_code
            task.error_summary = error_summary

        task = self._repo.update(task)
        self._repo.commit()

        logger.info(
            "Task transitioned: id=%s %s → %s (v%d)",
            task.id, current_status.value, target_status.value, task.version,
        )

        from app.services.audit_service import get_audit_service
        get_audit_service().record_task_lifecycle(
            task_id=task.id,
            event_type=f"task.{target_status.value.lower()}",
            outcome="FAILURE" if target_status == TaskStatus.FAILED else "SUCCESS",
            from_status=current_status.value,
            to_status=target_status.value,
            error_code=error_code,
            metadata={"error_summary": error_summary, "version": task.version},
            db=self._repo._db,
        )
        return task

    # ── Cancellation ─────────────────────────────────────────────

    def cancel_task(self, task_id: str) -> Task:
        """
        Cancel a task if its current state permits cancellation.

        Terminal tasks cannot be cancelled. Already-cancelled tasks return
        the existing state without error.
        """
        task = self.get_task(task_id)
        current_status = TaskStatus(task.status)

        # Idempotent: already cancelled
        if current_status == TaskStatus.CANCELLED:
            return task

        # Terminal states other than CANCELLED
        if current_status in TERMINAL_STATES:
            raise InvalidTaskTransitionError(
                current_status.value, TaskStatus.CANCELLED.value
            )

        # Check cancellable
        if current_status not in CANCELLABLE_STATES:
            raise InvalidTaskTransitionError(
                current_status.value, TaskStatus.CANCELLED.value
            )

        # Cancel any active run associated with this task so it does not continue running
        from app.services.run_service import RunService
        try:
            run_svc = RunService(self._repo._db)
            active_run = run_svc.get_active_run(task_id)
            if active_run:
                run_svc.cancel_run(active_run.id)
                logger.info(
                    "Cascaded cancellation to active run '%s' for task '%s'",
                    active_run.id,
                    task_id,
                )
        except Exception as exc:
            logger.warning(
                "Failed to cascade cancellation to active run for task '%s': %s",
                task_id,
                exc,
            )

        return self.transition_task(task_id, TaskStatus.CANCELLED.value)
