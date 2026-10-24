"""
Execution-run repository — data-access layer for ExecutionRun ORM model.

Follows the same pattern as ``TaskRepository``: pure data access, no
business logic.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.execution_run import ExecutionRun
from app.services.run_state_machine import ACTIVE_RUN_STATES


class RunRepository:
    """Encapsulates all database operations for the ExecutionRun model."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, run: ExecutionRun) -> ExecutionRun:
        """Insert a new run and flush to assign defaults."""
        self._db.add(run)
        self._db.flush()
        self._db.refresh(run)
        return run

    def get_by_id(self, run_id: str) -> Optional[ExecutionRun]:
        """Return a run by its ID, or None if not found."""
        return self._db.get(ExecutionRun, run_id)

    def get_active_run_for_task(self, task_id: str) -> Optional[ExecutionRun]:
        """
        Return the currently active (non-terminal) run for a task, if any.

        Uses a database query — not an in-memory flag.
        """
        active_statuses = [s.value for s in ACTIVE_RUN_STATES]
        query = (
            select(ExecutionRun)
            .where(ExecutionRun.task_id == task_id)
            .where(ExecutionRun.status.in_(active_statuses))
            .limit(1)
        )
        return self._db.execute(query).scalar_one_or_none()

    def list_runs_for_task(
        self,
        task_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExecutionRun], int]:
        """
        Return paginated runs for a task, newest first.

        Returns:
            A tuple of (runs, total_count).
        """
        base = select(ExecutionRun).where(ExecutionRun.task_id == task_id)
        count_query = select(func.count(ExecutionRun.id)).where(
            ExecutionRun.task_id == task_id
        )

        total = self._db.execute(count_query).scalar() or 0

        offset = (page - 1) * page_size
        query = base.order_by(ExecutionRun.created_at.desc()).offset(offset).limit(page_size)

        runs = list(self._db.execute(query).scalars().all())
        return runs, total

    def update(self, run: ExecutionRun) -> ExecutionRun:
        """Flush pending changes on a managed run instance."""
        self._db.flush()
        self._db.refresh(run)
        return run

    def commit(self) -> None:
        """Commit the current transaction."""
        self._db.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self._db.rollback()
