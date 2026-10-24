"""
Task ORM model.

Represents a generic task in the system. The task model is type-agnostic:
it stores a ``task_type`` identifier and a JSON ``configuration`` blob.
Actual task execution (booking, comparison, etc.) is handled by later phases.

Concurrency control uses an integer ``version`` column for optimistic locking.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _generate_uuid() -> str:
    """Return a new UUID4 as a string."""
    return str(uuid.uuid4())


class Task(Base):
    """
    Persistent task record.

    Fields:
        id: Stable unique identifier (UUID4 string).
        name: Optional human-readable label.
        task_type: Generic category (e.g. ``train_booking``).
        status: Current lifecycle state (managed by the state machine).
        description: Optional free-text description.
        configuration: Arbitrary validated JSON config for the task type.
        current_step: Name/id of the current logical step (future use).
        created_at: When the task was created (UTC).
        updated_at: Last modification time (UTC).
        started_at: When execution began (UTC, nullable).
        completed_at: When a terminal success state was reached (UTC, nullable).
        cancelled_at: When the task was cancelled (UTC, nullable).
        error_code: Machine-readable error code (nullable).
        error_summary: Sanitized human-readable error description (nullable).
        version: Integer for optimistic concurrency control.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_generate_uuid
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="CREATED", index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def __repr__(self) -> str:
        return (
            f"<Task id={self.id!r} type={self.task_type!r} "
            f"status={self.status!r} v={self.version}>"
        )
