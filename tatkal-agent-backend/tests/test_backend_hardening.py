"""
Tests for Phase 8 Backend Hardening, Integration Completion, and Demo Readiness.

Covers:
    - Task cancellation cascading to active execution runs.
    - Explicit run state transitions via POST /api/v1/runs/{run_id}/transition.
    - End-to-end run execution via POST /api/v1/runs/{run_id}/execute.
    - Immutability guards: completed/cancelled runs cannot be re-executed.
    - Readiness and liveness diagnostic endpoints.
    - Evidence capture and integrity verification upon run completion.
    - Enforcement of safety boundaries (live payment disabled, CAPTCHA human handoff).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestBackendHardening:
    """Hardening and workflow consistency test suite."""

    def test_task_cancellation_cascades_to_active_run(self, client: TestClient):
        """Cancelling a task must cascade cancellation to its active run."""
        # 1. Create a task
        task_resp = client.post(
            "/api/v1/tasks",
            json={
                "name": "Cascade cancellation task",
                "task_type": "train_booking",
                "description": "Test cascading cancellation",
                "configuration": {"route": "DEL-BOM"},
            },
        )
        assert task_resp.status_code == 201
        task_id = task_resp.json()["data"]["id"]

        # 2. Create an execution run (status: PENDING)
        run_resp = client.post(f"/api/v1/tasks/{task_id}/runs")
        assert run_resp.status_code == 201
        run_id = run_resp.json()["data"]["id"]
        assert run_resp.json()["data"]["status"] == "PENDING"

        # 3. Cancel the task
        cancel_resp = client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"

        # 4. Verify that the associated run is also CANCELLED
        get_run_resp = client.get(f"/api/v1/runs/{run_id}")
        assert get_run_resp.status_code == 200
        run_data = get_run_resp.json()["data"]
        assert run_data["status"] == "CANCELLED"
        assert run_data["ended_at"] is not None

    def test_run_manual_transition_api(self, client: TestClient):
        """Test POST /api/v1/runs/{run_id}/transition for state transitions."""
        # Create task and run
        t_resp = client.post(
            "/api/v1/tasks",
            json={"name": "Transition test", "task_type": "test_type"},
        )
        task_id = t_resp.json()["data"]["id"]
        r_resp = client.post(f"/api/v1/tasks/{task_id}/runs")
        run_id = r_resp.json()["data"]["id"]
        assert r_resp.json()["data"]["status"] == "PENDING"

        # Valid transition: PENDING -> RUNNING
        trans_resp = client.post(
            f"/api/v1/runs/{run_id}/transition",
            json={"target_status": "RUNNING"},
        )
        assert trans_resp.status_code == 200
        assert trans_resp.json()["data"]["status"] == "RUNNING"
        assert trans_resp.json()["data"]["started_at"] is not None

        # Invalid transition: RUNNING -> PENDING (not allowed by state machine)
        inv_resp = client.post(
            f"/api/v1/runs/{run_id}/transition",
            json={"target_status": "PENDING"},
        )
        assert inv_resp.status_code == 409

        # Transition nonexistent run -> 404
        nonexist_resp = client.post(
            "/api/v1/runs/nonexistent-uuid-1234/transition",
            json={"target_status": "COMPLETED"},
        )
        assert nonexist_resp.status_code == 404

    def test_run_execution_end_to_end_completion(self, client: TestClient):
        """Test complete sense-plan-act-verify execution via POST /api/v1/runs/{run_id}/execute."""
        # Create task and run
        t_resp = client.post(
            "/api/v1/tasks",
            json={
                "name": "End-to-end execution task",
                "task_type": "train_booking",
                "configuration": {"source": "NDLS", "destination": "BCT"},
            },
        )
        task_id = t_resp.json()["data"]["id"]

        r_resp = client.post(f"/api/v1/tasks/{task_id}/runs")
        run_id = r_resp.json()["data"]["id"]

        # Execute run
        exec_resp = client.post(
            f"/api/v1/runs/{run_id}/execute",
            json={"max_steps": 10, "timeout_seconds": 60.0},
        )
        assert exec_resp.status_code == 200
        run_data = exec_resp.json()["data"]
        assert run_data["status"] == "COMPLETED"
        assert run_data["ended_at"] is not None

        # Verify task is also COMPLETED
        t_get_resp = client.get(f"/api/v1/tasks/{task_id}")
        assert t_get_resp.status_code == 200
        assert t_get_resp.json()["data"]["status"] == "COMPLETED"

        # Verify execution summary evidence was created
        ev_resp = client.get(f"/api/v1/evidence?task_id={task_id}")
        assert ev_resp.status_code == 200
        ev_records = ev_resp.json()["data"]["records"]
        assert len(ev_records) >= 1
        summary_ev = next(r for r in ev_records if r["evidence_type"] == "EXECUTION_SUMMARY")
        assert summary_ev["run_id"] == run_id

        # Verify cryptographic integrity of the execution summary
        verify_resp = client.post(f"/api/v1/evidence/{summary_ev['id']}/verify")
        assert verify_resp.status_code == 200
        assert verify_resp.json()["data"]["status"] == "VERIFIED"
        assert verify_resp.json()["data"]["valid"] is True

    def test_completed_run_cannot_be_re_executed(self, client: TestClient):
        """Completed runs must be immutable and cannot be re-executed."""
        t_resp = client.post("/api/v1/tasks", json={"name": "Re-execute test", "task_type": "test"})
        task_id = t_resp.json()["data"]["id"]
        r_resp = client.post(f"/api/v1/tasks/{task_id}/runs")
        run_id = r_resp.json()["data"]["id"]

        # Complete the run
        exec_resp = client.post(f"/api/v1/runs/{run_id}/execute")
        assert exec_resp.status_code == 200
        assert exec_resp.json()["data"]["status"] == "COMPLETED"

        # Attempt re-execution
        re_exec_resp = client.post(f"/api/v1/runs/{run_id}/execute")
        assert re_exec_resp.status_code == 409  # Conflict: cannot transition terminal run

    def test_cancelled_run_cannot_be_executed(self, client: TestClient):
        """Cancelled runs cannot be executed."""
        t_resp = client.post("/api/v1/tasks", json={"name": "Cancel test", "task_type": "test"})
        task_id = t_resp.json()["data"]["id"]
        r_resp = client.post(f"/api/v1/tasks/{task_id}/runs")
        run_id = r_resp.json()["data"]["id"]

        cancel_resp = client.post(f"/api/v1/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["data"]["status"] == "CANCELLED"

        exec_resp = client.post(f"/api/v1/runs/{run_id}/execute")
        assert exec_resp.status_code == 409

    def test_liveness_and_readiness_endpoints(self, client: TestClient):
        """Test process liveness and readiness diagnostic endpoints."""
        # 1. Liveness
        live_resp = client.get("/api/v1/health/liveness")
        assert live_resp.status_code == 200
        live_data = live_resp.json()
        assert live_data["success"] is True
        assert live_data["data"]["status"] == "alive"

        # 2. Readiness
        ready_resp = client.get("/api/v1/health/readiness")
        assert ready_resp.status_code == 200
        ready_data = ready_resp.json()
        assert ready_data["success"] is True
        assert ready_data["data"]["status"] == "ready"
        assert ready_data["data"]["subsystems"]["database"] == "connected"
        assert ready_data["data"]["subsystems"]["storage"] == "ready"
        assert ready_data["data"]["subsystems"]["tool_registry"] == "ready"

    def test_safety_boundaries_enforced_in_phase8(self, client: TestClient):
        """Enforce that booking and payment safety boundaries remain completely active."""
        # 1. Booking assistance pauses before payment and enforces human handoff
        booking_resp = client.post(
            "/api/v1/booking/execute",
            json={
                "task_id": "test-task-safety",
                "passenger_count": 1,
                "journey_details": {
                    "train_number": "12001",
                    "travel_date": "2026-11-20",
                    "travel_class": "3A",
                },
            },
        )
        assert booking_resp.status_code == 200
        res_data = booking_resp.json()["data"]
        assert res_data["success"] is False
        assert res_data["evidence"]["requires_human"] is True
        assert "payment_authorization" in res_data["evidence"]["human_checkpoints"]

        # 2. Security adapter strictly prohibits auto-approving payment or CAPTCHA bypass
        sec_payment = client.post(
            "/api/v1/security/check",
            json={"action": "auto_approve_payment", "actor": "agent"},
        )
        assert sec_payment.status_code == 200
        assert sec_payment.json()["data"]["allowed"] is False
        assert "prohibited" in sec_payment.json()["data"]["reason"].lower()

        sec_captcha = client.post(
            "/api/v1/security/check",
            json={"action": "captcha_bypass", "actor": "agent"},
        )
        assert sec_captcha.status_code == 200
        assert sec_captcha.json()["data"]["allowed"] is False
