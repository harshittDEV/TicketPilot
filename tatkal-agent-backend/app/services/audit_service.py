"""
Audit service — business logic for recording and querying structured audit events (Phase 7).

Features:
- Validates and sanitizes event metadata with deep secret redaction.
- Persists audit events to the database using existing transaction boundaries.
- Emits structured log entries correlated with task_id, run_id, and correlation_id.
- Captures task/run lifecycle, tool/skill activity, recovery retries, circuit breaker transitions,
  and human-intervention requirements.
- Safe error handling: never crashes the caller or causes uncontrolled retry loops if audit logging fails.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_session
from app.integrations.security.redaction import redact_sensitive_data
from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)


class AuditError(Exception):
    """Base exception for audit operations."""


class AuditEventNotFoundError(AuditError):
    """Raised when an audit event cannot be found by ID."""


class AuditService:
    """
    Central service for recording, persisting, and querying structured audit events.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def record_event(
        self,
        *,
        event_type: str,
        event_category: str,
        outcome: str,
        source: str,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        tool_or_skill_name: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        evidence_references: Optional[list[str]] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        """
        Record and persist a structured audit event.

        Sanitizes all metadata before persistence, emits a structured log line,
        and safely catches persistence errors.
        """
        if not self._settings.audit_enabled:
            return None

        # Sanitize metadata payload
        safe_metadata = redact_sensitive_data(metadata) if metadata else None
        safe_evidence_refs = list(evidence_references) if evidence_references else None

        event = AuditEvent(
            id=str(uuid.uuid4()),
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            event_type=event_type,
            event_category=event_category.upper(),
            timestamp=datetime.now(timezone.utc),
            outcome=outcome.upper(),
            source=source,
            tool_or_skill_name=tool_or_skill_name,
            error_code=error_code,
            event_metadata=safe_metadata,
            evidence_references=safe_evidence_refs,
            schema_version=1,
        )

        # Log structured record
        logger.info(
            "AUDIT | %s | %s | task=%s run=%s outcome=%s source=%s err=%s",
            event.event_category,
            event.event_type,
            event.task_id or "-",
            event.run_id or "-",
            event.outcome,
            event.source,
            event.error_code or "-",
        )

        # Persist to database
        if db is not None:
            try:
                db.add(event)
                db.commit()
                db.refresh(event)
                return event
            except Exception as exc:
                logger.error("Failed to persist audit event '%s': %s", event_type, exc)
                try:
                    db.rollback()
                except Exception:
                    pass
                return event

        # If db session was not supplied, use a short-lived session
        try:
            with get_session() as session:
                session.add(event)
                session.commit()
                session.refresh(event)
                return event
        except Exception as exc:
            logger.error("Failed to persist audit event '%s' via internal session: %s", event_type, exc)
            return event

    # ── Convenience Helpers ──────────────────────────────────────────

    def record_task_lifecycle(
        self,
        *,
        task_id: str,
        event_type: str,
        outcome: str = "SUCCESS",
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        meta = dict(metadata or {})
        if from_status:
            meta["from_status"] = from_status
        if to_status:
            meta["to_status"] = to_status
        return self.record_event(
            event_type=event_type,
            event_category="TASK",
            outcome=outcome,
            source="task_service",
            task_id=task_id,
            error_code=error_code,
            metadata=meta,
            db=db,
        )

    def record_run_lifecycle(
        self,
        *,
        run_id: str,
        task_id: str,
        event_type: str,
        outcome: str = "SUCCESS",
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        meta = dict(metadata or {})
        if from_status:
            meta["from_status"] = from_status
        if to_status:
            meta["to_status"] = to_status
        return self.record_event(
            event_type=event_type,
            event_category="RUN",
            outcome=outcome,
            source="run_service",
            task_id=task_id,
            run_id=run_id,
            error_code=error_code,
            metadata=meta,
            db=db,
        )

    def record_tool_execution(
        self,
        *,
        run_id: str,
        task_id: str,
        tool_name: str,
        action_type: str,
        outcome: str,
        parameters: Optional[dict[str, Any]] = None,
        result_status: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        error_code: Optional[str] = None,
        evidence_references: Optional[list[str]] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        meta: dict[str, Any] = {
            "action_type": action_type,
            "parameters": parameters,
            "result_status": result_status,
            "duration_seconds": duration_seconds,
        }
        return self.record_event(
            event_type=f"tool.execution.{outcome.lower()}",
            event_category="TOOL",
            outcome=outcome,
            source="tool_executor",
            task_id=task_id,
            run_id=run_id,
            tool_or_skill_name=tool_name,
            error_code=error_code,
            metadata=meta,
            evidence_references=evidence_references,
            db=db,
        )

    def record_skill_execution(
        self,
        *,
        run_id: Optional[str],
        task_id: Optional[str],
        skill_name: str,
        outcome: str,
        inputs: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        meta: dict[str, Any] = {
            "inputs": inputs,
            "error": error,
        }
        return self.record_event(
            event_type=f"skill.execution.{outcome.lower()}",
            event_category="SKILL",
            outcome=outcome,
            source="skill_executor",
            task_id=task_id,
            run_id=run_id,
            tool_or_skill_name=skill_name,
            error_code="SKILL_ERROR" if outcome.upper() == "FAILURE" else None,
            metadata=meta,
            db=db,
        )

    def record_recovery_event(
        self,
        *,
        task_id: Optional[str],
        run_id: Optional[str],
        event_type: str,
        error_category: str,
        error_code: str,
        decision: str,
        backoff_seconds: Optional[float] = None,
        attempt: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        meta: dict[str, Any] = {
            "error_category": error_category,
            "decision": decision,
            "backoff_seconds": backoff_seconds,
            "attempt": attempt,
        }
        return self.record_event(
            event_type=event_type,
            event_category="RECOVERY",
            outcome="SUCCESS" if decision == "RETRY" else "FAILURE",
            source="recovery_policy",
            task_id=task_id,
            run_id=run_id,
            error_code=error_code,
            metadata=meta,
            db=db,
        )

    def record_circuit_breaker_event(
        self,
        *,
        breaker_name: str,
        from_state: str,
        to_state: str,
        metrics: Optional[dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        meta: dict[str, Any] = {
            "breaker_name": breaker_name,
            "from_state": from_state,
            "to_state": to_state,
            "metrics": metrics,
        }
        event_name = f"recovery.circuit_{to_state.lower()}"
        return self.record_event(
            event_type=event_name,
            event_category="RECOVERY",
            outcome="WARNING" if to_state == "OPEN" else "SUCCESS",
            source="circuit_breaker",
            tool_or_skill_name=breaker_name,
            metadata=meta,
            db=db,
        )

    def record_human_intervention(
        self,
        *,
        task_id: Optional[str],
        run_id: Optional[str],
        reason: str,
        context: Optional[dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> Optional[AuditEvent]:
        meta = dict(context or {})
        meta["reason"] = reason
        return self.record_event(
            event_type="human_intervention.required",
            event_category="RUN",
            outcome="PENDING",
            source="agent_orchestrator",
            task_id=task_id,
            run_id=run_id,
            error_code="HUMAN_INTERVENTION_REQUIRED",
            metadata=meta,
            db=db,
        )

    # ── Query API ────────────────────────────────────────────────────

    def get_event(self, db: Session, event_id: str) -> AuditEvent:
        """Fetch a single audit event by ID or raise AuditEventNotFoundError."""
        event = db.get(AuditEvent, event_id)
        if not event:
            raise AuditEventNotFoundError(f"Audit event '{event_id}' not found")
        return event

    def list_events(
        self,
        db: Session,
        *,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        event_type: Optional[str] = None,
        event_category: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditEvent], int]:
        """List audit events with deterministic ordering and optional filtering."""
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        stmt = select(AuditEvent)
        if task_id:
            stmt = stmt.where(AuditEvent.task_id == task_id)
        if run_id:
            stmt = stmt.where(AuditEvent.run_id == run_id)
        if event_type:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if event_category:
            stmt = stmt.where(AuditEvent.event_category == event_category.upper())
        if start_time:
            stmt = stmt.where(AuditEvent.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(AuditEvent.timestamp <= end_time)

        # Count total matches
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        # Deterministic sorting: latest first, then ID
        stmt = stmt.order_by(AuditEvent.timestamp.desc(), AuditEvent.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(db.scalars(stmt).all())

        return items, total


# Singleton accessor helper
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Return the global AuditService instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service


def reset_audit_service() -> None:
    """Reset the global AuditService instance."""
    global _audit_service
    _audit_service = None
