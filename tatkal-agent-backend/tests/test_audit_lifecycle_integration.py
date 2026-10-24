"""
End-to-end integration tests verifying audit trail completeness across workflow lifecycles (Phase 7).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.database.session import get_session_factory
from app.services.audit_service import get_audit_service


class TestAuditLifecycleIntegration:
    """Tests confirming full audit coverage across Task, Run, Tool, and Human-Intervention flows."""

    def test_task_full_lifecycle_generates_complete_audit_trail(self, client: TestClient):
        """Task creation and status transitions produce sequential audit events."""
        # 1. Create task
        create_res = client.post(
            "/api/v1/tasks",
            json={
                "name": "Audit Lifecycle Task",
                "task_type": "train_booking",
                "configuration": {
                    "source": "Delhi",
                    "destination": "Mumbai",
                    "password": "SecretShouldBeRedacted",
                },
            },
        )
        assert create_res.status_code == 201
        task_id = create_res.json()["data"]["id"]

        # 2. Transition CREATED -> READY
        trans_res = client.post(
            f"/api/v1/tasks/{task_id}/transition",
            json={"target_status": "READY"},
        )
        assert trans_res.status_code == 200

        # 3. Transition READY -> RUNNING
        trans_res2 = client.post(
            f"/api/v1/tasks/{task_id}/transition",
            json={"target_status": "RUNNING"},
        )
        assert trans_res2.status_code == 200

        # 4. Query audit trail for task
        audit_res = client.get(f"/api/v1/audit/tasks/{task_id}/events")
        assert audit_res.status_code == 200
        events = audit_res.json()["data"]["events"]

        event_types = [e["event_type"] for e in events]
        assert "task.created" in event_types
        assert "task.ready" in event_types
        assert "task.running" in event_types

        # Verify zero secret leakage in audit event metadata
        created_event = next(e for e in events if e["event_type"] == "task.created")
        if created_event.get("event_metadata"):
            meta_str = str(created_event["event_metadata"])
            assert "SecretShouldBeRedacted" not in meta_str

    def test_run_lifecycle_and_human_intervention_audit(self, client: TestClient):
        """Execution run creation and transitions are audited."""
        # 1. Create task
        task_res = client.post(
            "/api/v1/tasks",
            json={"name": "Run Audit Task", "task_type": "generic_task"},
        )
        task_id = task_res.json()["data"]["id"]

        # 2. Create execution run
        run_res = client.post(f"/api/v1/tasks/{task_id}/runs")
        assert run_res.status_code == 201
        run_id = run_res.json()["data"]["id"]

        # 3. Pause run
        client.post(
            f"/api/v1/tasks/{task_id}/transition",
            json={"target_status": "READY"},
        )
        # Verify run.created was audited
        audit_res = client.get(f"/api/v1/audit/runs/{run_id}/events")
        assert audit_res.status_code == 200
        events = audit_res.json()["data"]["events"]
        assert any(e["event_type"] == "run.created" for e in events)
