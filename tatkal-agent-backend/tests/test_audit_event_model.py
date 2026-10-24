"""
Unit tests for AuditEvent and EvidenceRecord SQLAlchemy models (Phase 7).
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.session import get_engine, get_session_factory, reset_engine
from app.models.audit import AuditEvent, EvidenceRecord


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


class TestAuditEventModel:
    """Tests for the AuditEvent ORM model."""

    def test_create_audit_event_model_defaults(self):
        """AuditEvent generates UUID, UTC timestamp, and default outcome."""
        event = AuditEvent(
            event_type="test.event",
            event_category="TEST",
            source="unit_test",
        )
        assert event.id is not None
        assert len(event.id) == 36
        assert event.timestamp is not None
        assert event.outcome == "SUCCESS"
        assert event.schema_version == 1

    def test_audit_event_persistence_and_retrieval(self, db_session: Session):
        """AuditEvent persists to database and queries back correctly."""
        event = AuditEvent(
            task_id="task-123",
            run_id="run-456",
            correlation_id="corr-789",
            event_type="task.created",
            event_category="TASK",
            outcome="SUCCESS",
            source="task_service",
            tool_or_skill_name=None,
            error_code=None,
            event_metadata={"task_type": "train_booking"},
            evidence_references=["ev-001"],
        )
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        loaded = db_session.get(AuditEvent, event_id)
        assert loaded is not None
        assert loaded.task_id == "task-123"
        assert loaded.run_id == "run-456"
        assert loaded.correlation_id == "corr-789"
        assert loaded.event_type == "task.created"
        assert loaded.event_category == "TASK"
        assert loaded.event_metadata == {"task_type": "train_booking"}
        assert loaded.evidence_references == ["ev-001"]


class TestEvidenceRecordModel:
    """Tests for the EvidenceRecord ORM model."""

    def test_create_evidence_record_defaults(self):
        """EvidenceRecord initializes with UUID, timestamp, and default status."""
        record = EvidenceRecord(
            evidence_type="SCREENSHOT",
            file_path="evidence/screen_01.png",
            file_size_bytes=1024,
            sha256_checksum="abc123def456",
            capture_source="browser_adapter",
        )
        assert record.id is not None
        assert len(record.id) == 36
        assert record.integrity_status == "VERIFIED"
        assert record.content_type == "application/octet-stream"

    def test_evidence_record_persistence_and_retrieval(self, db_session: Session):
        """EvidenceRecord persists and can be queried with relationships."""
        record = EvidenceRecord(
            task_id="task-999",
            run_id="run-888",
            audit_event_id="audit-777",
            evidence_type="DOM_SNAPSHOT",
            file_path="evidence/dom_999.json",
            content_type="application/json",
            file_size_bytes=4096,
            sha256_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            capture_source="observer",
            metadata_payload={"url": "https://irctc.co.in"},
            integrity_status="VERIFIED",
        )
        db_session.add(record)
        db_session.commit()
        rec_id = record.id

        loaded = db_session.get(EvidenceRecord, rec_id)
        assert loaded is not None
        assert loaded.task_id == "task-999"
        assert loaded.evidence_type == "DOM_SNAPSHOT"
        assert loaded.sha256_checksum.startswith("e3b0c442")
        assert loaded.metadata_payload == {"url": "https://irctc.co.in"}
