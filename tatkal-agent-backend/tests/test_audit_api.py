"""
Integration tests for Audit and Evidence REST API endpoints (Phase 7).
"""

from __future__ import annotations

import hashlib
from fastapi.testclient import TestClient
import pytest

from app.database.session import get_session_factory
from app.services.audit_service import get_audit_service
from app.services.evidence_service import get_evidence_service


class TestAuditApiEndpoints:
    """Tests for /api/v1/audit routes."""

    def test_list_audit_events_endpoint(self, client: TestClient):
        """GET /api/v1/audit/events returns standard ApiResponse with events and pagination."""
        # 1. Create a task via API to trigger task.created audit event
        task_res = client.post(
            "/api/v1/tasks",
            json={
                "name": "Audit Test Task",
                "task_type": "train_booking",
                "configuration": {"source": "Delhi", "destination": "Mumbai"},
            },
        )
        assert task_res.status_code == 201
        task_id = task_res.json()["data"]["id"]

        # 2. Query audit events
        res = client.get(f"/api/v1/audit/events?task_id={task_id}")
        assert res.status_code == 200
        payload = res.json()
        assert payload["success"] is True
        events = payload["data"]["events"]
        assert len(events) >= 1
        assert events[0]["event_type"] == "task.created"
        assert events[0]["task_id"] == task_id
        assert payload["data"]["meta"]["total"] >= 1

    def test_get_single_audit_event_by_id(self, client: TestClient):
        """GET /api/v1/audit/events/{id} returns single event or 404."""
        # Seed an audit event directly
        service = get_audit_service()
        factory = get_session_factory()
        with factory() as session:
            ev = service.record_event(
                event_type="custom.action",
                event_category="TEST",
                outcome="SUCCESS",
                source="api_test",
                metadata={"foo": "bar"},
                db=session,
            )
            event_id = ev.id

        # Success query
        res = client.get(f"/api/v1/audit/events/{event_id}")
        assert res.status_code == 200
        assert res.json()["data"]["id"] == event_id
        assert res.json()["data"]["event_metadata"]["foo"] == "bar"

        # Not found
        res_404 = client.get("/api/v1/audit/events/non-existent-uuid")
        assert res_404.status_code == 404

    def test_get_task_and_run_specific_events(self, client: TestClient):
        """GET /api/v1/audit/tasks/{task_id}/events returns events scoped to task."""
        task_res = client.post(
            "/api/v1/tasks",
            json={"name": "Scoped Task", "task_type": "test_type"},
        )
        task_id = task_res.json()["data"]["id"]

        res = client.get(f"/api/v1/audit/tasks/{task_id}/events")
        assert res.status_code == 200
        assert res.json()["data"]["meta"]["total"] >= 1


class TestEvidenceApiEndpoints:
    """Tests for /api/v1/evidence routes."""

    def test_list_and_get_evidence_metadata(self, client: TestClient, tmp_path):
        """GET /api/v1/evidence lists records and /api/v1/evidence/{id} returns metadata."""
        ev_service = get_evidence_service()
        factory = get_session_factory()
        with factory() as session:
            record = ev_service.capture_evidence(
                session,
                data=b"test-screenshot-bytes",
                evidence_type="SCREENSHOT",
                content_type="image/png",
                task_id="t-ev-api",
            )
            ev_id = record.id

        # List
        list_res = client.get(f"/api/v1/evidence?task_id=t-ev-api")
        assert list_res.status_code == 200
        assert list_res.json()["data"]["meta"]["total"] == 1
        assert list_res.json()["data"]["records"][0]["id"] == ev_id

        # Detail
        detail_res = client.get(f"/api/v1/evidence/{ev_id}")
        assert detail_res.status_code == 200
        assert detail_res.json()["data"]["evidence_type"] == "SCREENSHOT"
        assert detail_res.json()["data"]["content_type"] == "image/png"

    def test_verify_evidence_integrity_endpoint(self, client: TestClient):
        """POST /api/v1/evidence/{id}/verify recalculates and checks SHA-256."""
        ev_service = get_evidence_service()
        factory = get_session_factory()
        data = b'{"dom": "<div id=\'login\'></div>"}'
        expected_hash = hashlib.sha256(data).hexdigest()

        with factory() as session:
            record = ev_service.capture_evidence(
                session,
                data=data,
                evidence_type="DOM_SNAPSHOT",
                content_type="application/json",
            )
            ev_id = record.id

        res = client.post(f"/api/v1/evidence/{ev_id}/verify")
        assert res.status_code == 200
        payload = res.json()["data"]
        assert payload["valid"] is True
        assert payload["status"] == "VERIFIED"
        assert payload["stored_checksum"] == expected_hash
        assert payload["computed_checksum"] == expected_hash

    def test_download_evidence_artifact_safe(self, client: TestClient):
        """GET /api/v1/evidence/{id}/download streams binary content with headers."""
        ev_service = get_evidence_service()
        factory = get_session_factory()
        raw_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest"

        with factory() as session:
            record = ev_service.capture_evidence(
                session,
                data=raw_bytes,
                evidence_type="SCREENSHOT",
                content_type="image/png",
            )
            ev_id = record.id

        res = client.get(f"/api/v1/evidence/{ev_id}/download")
        assert res.status_code == 200
        assert res.content == raw_bytes
        assert res.headers["content-type"] == "image/png"
        assert "inline; filename=" in res.headers["content-disposition"]
        assert res.headers["x-evidence-checksum"] == record.sha256_checksum

    def test_download_evidence_nonexistent_returns_404(self, client: TestClient):
        """GET /api/v1/evidence/{id}/download returns 404 for unknown evidence IDs."""
        res = client.get("/api/v1/evidence/00000000-0000-0000-0000-000000000000/download")
        assert res.status_code == 404
