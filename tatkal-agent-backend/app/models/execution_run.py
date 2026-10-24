"""
Execution Run ORM model.

Represents a single attempt to execute a Task.  A Task may have many
historical runs, but only one run can be *active* (non-terminal) at a time.

Active-run enforcement is handled at the service level using a
database-level query guard (not an in-memory flag).

Concurrency control uses an integer ``version`` column for optimistic
locking, consistent with the Task model convention.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _generate_uuid() -> str:
    """Return a new UUID4 as a string."""
    return str(uuid.uuid4())


class ExecutionRun(Base):
    """
    Persistent execution-run record.

    Fields:
        id:             Unique run identifier (UUID4 string).
        task_id:        Foreign key linking to the parent task.
        status:         Current run lifecycle state (managed by RunStateMachine).
        current_step:   Name/id of the current logical step (nullable).
        steps_completed: Counter of actions/steps completed in this run.
        started_at:     When the run began executing (UTC, nullable).
        ended_at:       When the run reached a terminal state (UTC, nullable).
        created_at:     When the run record was created (UTC).
        updated_at:     Last modification time (UTC).
        error_code:     Machine-readable error code (nullable).
        error_summary:  Sanitised human-readable error description (nullable).
        version:        Integer for optimistic concurrency control.
    """

    __tablename__ = "execution_runs"

    # ── Identity ─────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_generate_uuid
    )
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Status ───────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING", index=True
    )
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)
    steps_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Timestamps ───────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Error information ────────────────────────────────────────
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Concurrency ──────────────────────────────────────────────
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ── Relationships ────────────────────────────────────────────
    task = relationship("Task", backref="execution_runs", lazy="select")

    # ── Composite index for active-run guard ─────────────────────
    __table_args__ = (
        Index("ix_execution_runs_task_status", "task_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExecutionRun id={self.id!r} task={self.task_id!r} "
            f"status={self.status!r} steps={self.steps_completed} v={self.version}>"
        )
