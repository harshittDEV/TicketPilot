"""
Audit Event and Evidence Record ORM models (Phase 7).

Provides persistent, structured records for:
- Traceable agent execution and tool/skill activity.
- Task and execution-run state transitions.
- Recovery decisions, retries, and circuit breaker state changes.
- Human-intervention requirements.
- Associated evidence artifacts with SHA-256 integrity checksums.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _generate_uuid() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


class AuditEvent(Base):
    """
    Persistent audit event record.

    Captures traceable lifecycle, tool, skill, recovery, and security events.
    Metadata is strictly sanitized of sensitive credentials before persistence.
    """

    __tablename__ = "audit_events"

    # ── Identity ─────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_generate_uuid
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )

    # ── Event Classification ─────────────────────────────────────
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    event_category: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )
    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SUCCESS"
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    tool_or_skill_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    # ── Structured Context ───────────────────────────────────────
    event_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    evidence_references: Mapped[Optional[list[str]]] = mapped_column(
        JSON, nullable=True
    )
    schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )

    # ── Composite Indexes ────────────────────────────────────────
    __table_args__ = (
        Index("ix_audit_events_task_timestamp", "task_id", "timestamp"),
        Index("ix_audit_events_run_timestamp", "run_id", "timestamp"),
        Index("ix_audit_events_type_timestamp", "event_type", "timestamp"),
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("id", _generate_uuid())
        kwargs.setdefault("timestamp", _utcnow())
        kwargs.setdefault("outcome", "SUCCESS")
        kwargs.setdefault("schema_version", 1)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<AuditEvent id={self.id!r} type={self.event_type!r} "
            f"task={self.task_id!r} run={self.run_id!r} outcome={self.outcome!r}>"
        )


class EvidenceRecord(Base):
    """
    Persistent metadata record for evidence artifacts.

    Links stored files (e.g. screenshots, DOM excerpts, execution summaries)
    to tasks, runs, and audit events, recording their SHA-256 checksums
    for tamper detection.
    """

    __tablename__ = "evidence_records"

    # ── Identity ─────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_generate_uuid
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    audit_event_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )

    # ── Classification & Metadata ────────────────────────────────
    evidence_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )
    file_path: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    content_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="application/octet-stream"
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    sha256_checksum: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    capture_source: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    metadata_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    integrity_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="VERIFIED"
    )

    # ── Composite Indexes ────────────────────────────────────────
    __table_args__ = (
        Index("ix_evidence_records_task_timestamp", "task_id", "timestamp"),
        Index("ix_evidence_records_run_timestamp", "run_id", "timestamp"),
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("id", _generate_uuid())
        kwargs.setdefault("timestamp", _utcnow())
        kwargs.setdefault("content_type", "application/octet-stream")
        kwargs.setdefault("integrity_status", "VERIFIED")
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<EvidenceRecord id={self.id!r} type={self.evidence_type!r} "
            f"size={self.file_size_bytes} status={self.integrity_status!r}>"
        )
