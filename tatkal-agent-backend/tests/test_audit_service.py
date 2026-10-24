"""
Unit tests for AuditService event capture, sanitization, and query capabilities (Phase 7).
"""

from __future__ import annotations

import pytest

from app.database.base import Base
from app.database.session import get_engine, get_session_factory, reset_engine
from app.services.audit_service import AuditEventNotFoundError, AuditService


@pytest.fixture()
def db_session(tmp_db_url: str):
    """Provides a clean, isolated SQLite database session for unit tests."""
    reset_engine()
    engine = get_engine(tmp_db_url)
    Base.metadata.create_all(bind=engine)
    factory = get_session_factory(engine)
    with factory() as session:
        yield session
    reset_engine()


class TestAuditService:
    """Tests for structured audit event recording and query operations."""

    def test_record_event_sanitizes_metadata_automatically(self, db_session):
        """AuditService redacts passwords, tokens, and cards before saving metadata."""
        service = AuditService()

        event = service.record_event(
            event_type="test.action",
            event_category="TEST",
            outcome="SUCCESS",
            source="test_suite",
            task_id="t-1",
            metadata={
                "username": "alice",
                "password": "MySecretPassword!",
                "api_key": "sk-123456",
                "safe_field": "public_value",
            },
            db=db_session,
        )
        event_id = event.id

        loaded = service.get_event(db_session, event_id)
        assert loaded.event_metadata["password"] == "[REDACTED]"
        assert loaded.event_metadata["api_key"] == "[REDACTED]"
        assert loaded.event_metadata["username"] == "alice"
        assert loaded.event_metadata["safe_field"] == "public_value"

    def test_record_task_and_run_lifecycle_helpers(self, db_session):
        """Helper methods record structured task and run lifecycle transitions."""
        service = AuditService()

        service.record_task_lifecycle(
            task_id="task-lifecycle-1",
            event_type="task.created",
            outcome="SUCCESS",
            to_status="CREATED",
            db=db_session,
        )
        service.record_run_lifecycle(
            run_id="run-lifecycle-1",
            task_id="task-lifecycle-1",
            event_type="run.started",
            outcome="SUCCESS",
            from_status="PENDING",
            to_status="RUNNING",
            db=db_session,
        )

        task_events, total = service.list_events(db_session, task_id="task-lifecycle-1")
        assert total == 2
        types = {e.event_type for e in task_events}
        assert "task.created" in types
        assert "run.started" in types

    def test_record_recovery_and_circuit_breaker_events(self, db_session):
        """Records recovery retry scheduling and circuit breaker state changes."""
        service = AuditService()

        service.record_recovery_event(
            task_id="t-rec",
            run_id="r-rec",
            event_type="recovery.retry_scheduled",
            error_category="TRANSIENT_NETWORK",
            error_code="NETWORK_ERROR",
            decision="RETRY",
            backoff_seconds=1.0,
            attempt=2,
            db=db_session,
        )
        service.record_circuit_breaker_event(
            breaker_name="train_comparison",
            from_state="CLOSED",
            to_state="OPEN",
            metrics={"failure_count": 5},
            db=db_session,
        )

        events, total = service.list_events(db_session, event_category="RECOVERY")
        assert total == 2
        cb_event = next(e for e in events if e.event_type == "recovery.circuit_open")
        assert cb_event.tool_or_skill_name == "train_comparison"
        assert cb_event.event_metadata["from_state"] == "CLOSED"
        assert cb_event.event_metadata["to_state"] == "OPEN"

    def test_record_human_intervention(self, db_session):
        """Records human intervention requirement events."""
        service = AuditService()

        service.record_human_intervention(
            task_id="t-gate",
            run_id="r-gate",
            reason="IRCTC CAPTCHA challenge detected",
            context={"step": 4, "tool": "browser"},
            db=db_session,
        )

        events, total = service.list_events(db_session, event_type="human_intervention.required")
        assert total == 1
        assert events[0].outcome == "PENDING"
        assert events[0].error_code == "HUMAN_INTERVENTION_REQUIRED"
        assert events[0].event_metadata["reason"] == "IRCTC CAPTCHA challenge detected"

    def test_list_events_pagination_and_deterministic_order(self, db_session):
        """Events are paginated and sorted latest first."""
        service = AuditService()

        for i in range(15):
            service.record_event(
                event_type=f"batch.event.{i}",
                event_category="TEST",
                outcome="SUCCESS",
                source="batch_test",
                task_id="t-batch",
                db=db_session,
            )

        page1, total = service.list_events(db_session, task_id="t-batch", page=1, page_size=10)
        assert total == 15
        assert len(page1) == 10

        page2, _ = service.list_events(db_session, task_id="t-batch", page=2, page_size=10)
        assert len(page2) == 5

        # Deterministic latest first
        assert page1[0].timestamp >= page1[1].timestamp
