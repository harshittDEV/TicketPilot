"""
Tests for Teammate Integration API endpoints (/api/v1/integrations, /trains, /scheduler, /security, /booking).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from app.integrations.booking.adapter import BookingAssistanceAdapter
from app.integrations.registry import get_registry
from app.integrations.scheduler.adapter import TatkalSchedulerAdapter
from app.integrations.security.adapter import SecurityAdapter
from app.integrations.train_comparison.adapter import TrainComparisonAdapter
from app.main import app


@pytest.fixture
def client():
    registry = get_registry()
    if not registry.is_registered("scheduler"):
        registry.register("scheduler", TatkalSchedulerAdapter(), force=True)
    if not registry.is_registered("train_comparison"):
        registry.register("train_comparison", TrainComparisonAdapter(), force=True)
    if not registry.is_registered("security"):
        registry.register("security", SecurityAdapter(), force=True)
    if not registry.is_registered("booking_assistance"):
        registry.register("booking_assistance", BookingAssistanceAdapter(), force=True)

    with TestClient(app) as test_client:
        yield test_client


class TestIntegrationApiEndpoints:
    """Verify integration discovery, health, and functionality endpoints."""

    def test_list_integrations_returns_200(self, client):
        response = client.get("/api/v1/integrations")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        names = [item["name"] for item in body["data"]]
        assert "scheduler" in names
        assert "train_comparison" in names
        assert "security" in names
        assert "booking_assistance" in names

    def test_integration_health_success(self, client):
        response = client.get("/api/v1/integrations/scheduler/health")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["integration"] == "scheduler"
        assert body["data"]["healthy"] is True

    def test_unknown_integration_health_returns_404(self, client):
        response = client.get("/api/v1/integrations/unknown_module_xyz/health")
        assert response.status_code == 404

    def test_train_comparison_endpoint(self, client):
        response = client.post(
            "/api/v1/trains/compare",
            json={
                "source_station": "Roorkee",
                "destination_station": "Haridwar",
                "travel_date": "2026-11-20",
                "quota": "TATKAL",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        candidates = body["data"]["candidates"]
        assert len(candidates) >= 2
        # First train is cheapest 12002
        assert candidates[0]["train_number"] == "12002"

    def test_scheduler_calculate_endpoint(self, client):
        response = client.post(
            "/api/v1/scheduler/calculate",
            json={
                "journey_date": "2026-11-20",
                "travel_class": "SL",
                "reminder_minutes_before": 5,
            },
        )
        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert data["opening_date"] == "2026-11-19"
        assert data["opening_time_ist"] == "11:00"

    def test_scheduler_schedule_and_cancel_endpoints(self, client):
        future_iso = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        create_res = client.post(
            "/api/v1/scheduler/schedule",
            json={
                "task_id": "api_test_task",
                "execute_at": future_iso,
            },
        )
        assert create_res.status_code == 200
        sched_id = create_res.json()["data"]["schedule_id"]
        assert sched_id.startswith("sched_")

        # Cancel the scheduled run
        cancel_res = client.delete(f"/api/v1/scheduler/{sched_id}")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["data"]["status"] == "cancelled"

    def test_security_check_endpoint(self, client):
        # 1. Prohibited action
        res_bad = client.post(
            "/api/v1/security/check",
            json={"action": "captcha_bypass", "actor": "bot"},
        )
        assert res_bad.status_code == 200
        assert res_bad.json()["data"]["allowed"] is False

        # 2. Permitted action
        res_good = client.post(
            "/api/v1/security/check",
            json={"action": "view_trains", "actor": "agent"},
        )
        assert res_good.status_code == 200
        assert res_good.json()["data"]["allowed"] is True

    def test_security_redact_endpoint(self, client):
        response = client.post(
            "/api/v1/security/redact",
            json={
                "payload": {
                    "username": "user1",
                    "password": "secretPassword",
                    "passengerName": "John Doe",
                }
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["username"] == "user1"
        assert data["password"] == "[REDACTED]"
        assert data["passengerName"] == "[REDACTED]"

    def test_booking_plan_and_execute_endpoints(self, client):
        plan_res = client.post(
            "/api/v1/booking/plan",
            json={
                "task_id": "api_book_task",
                "passenger_count": 2,
                "journey_details": {
                    "train_number": "12002",
                    "travel_date": "2026-11-20",
                    "travel_class": "CC",
                },
            },
        )
        assert plan_res.status_code == 200
        plan = plan_res.json()["data"]
        assert plan["task_id"] == "api_book_task"
        assert len(plan["steps"]) == 5

        # Execute booking assistance - enforces human handoff
        exec_res = client.post(
            "/api/v1/booking/execute",
            json={
                "task_id": "api_book_task",
                "passenger_count": 2,
                "journey_details": {
                    "train_number": "12002",
                    "travel_date": "2026-11-20",
                    "travel_class": "CC",
                },
            },
        )
        assert exec_res.status_code == 200
        exec_body = exec_res.json()["data"]
        assert exec_body["success"] is False
        assert exec_body["evidence"]["status"] == "AWAITING_HUMAN_INTERVENTION"
