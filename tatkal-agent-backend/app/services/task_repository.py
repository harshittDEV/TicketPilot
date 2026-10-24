"""
Task repository — data-access layer for Task ORM model.

All database queries for tasks live here. Business logic stays in the service.
"""

from __future__ import annotations

import math
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.task import Task


class TaskRepository:
    """Encapsulates all database operations for the Task model."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, task: Task) -> Task:
        """Insert a new task and flush to assign defaults."""
        self._db.add(task)
        self._db.flush()
        self._db.refresh(task)
        return task

    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Return a task by its ID, or None if it does not exist."""
        return self._db.get(Task, task_id)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        task_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Task], int]:
        """
        Return a paginated list of tasks with optional filters.

        Returns:
            A tuple of (tasks, total_count).
        """
        query = select(Task)
        count_query = select(func.count(Task.id))

        if status:
            query = query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)
        if task_type:
            query = query.where(Task.task_type == task_type)
            count_query = count_query.where(Task.task_type == task_type)

        total = self._db.execute(count_query).scalar() or 0

        offset = (page - 1) * page_size
        query = query.order_by(Task.created_at.desc()).offset(offset).limit(page_size)

        tasks = list(self._db.execute(query).scalars().all())
        return tasks, total

    def update(self, task: Task) -> Task:
        """Flush pending changes on a managed task instance."""
        self._db.flush()
        self._db.refresh(task)
        return task

    def commit(self) -> None:
        """Commit the current transaction."""
        self._db.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        self._db.rollback()
