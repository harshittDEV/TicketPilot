"""
Unit and integration tests for the Autonomous Tatkal Booking Agent.

Tests:
1. Journey configuration schemas and passenger validation rules.
2. 12-point pre-flight preparation service (TaskPreparationService).
3. Preparation API endpoint (POST /api/v1/tasks/{task_id}/prepare).
4. Scheduling API endpoints (POST /api/v1/tasks/{task_id}/schedule, unschedule).
5. Autonomous execution loop with TatkalBookingAgentPlanner.
6. Halting at CAPTCHA barrier with WAITING_FOR_HUMAN transition.
7. Halting at payment boundary with AWAITING_PAYMENT_APPROVAL transition.
8. Safety assertion: payment execution remains strictly disabled.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agent.booking_planner import TatkalBookingAgentPlanner
from app.agent.llm.base import LLMRequest
from app.agent.models import ActionType, PlannerRequest
from app.database.session import get_session_factory
from app.models.task import Task
from app.schemas.journey import (
    BerthPreference,
    Gender,
    JourneyConfiguration,
    PassengerDetails,
    QuotaType,
)
from app.services.preparation_service import TaskPreparationService
from app.services.run_service import RunService
from app.services.task_service import TaskService
from app.services.task_state_machine import TaskStatus


class TestJourneyConfigurationValidation:
    """Test journey and passenger schema validation."""

    def test_valid_passenger_details(self):
        p = PassengerDetails(
            name="Rahul Sharma",
            age=34,
            gender=Gender.MALE,
            berth_preference=BerthPreference.LOWER,
        )
        assert p.name == "Rahul Sharma"
        assert p.age == 34
        assert p.gender == Gender.MALE
        assert p.berth_preference == BerthPreference.LOWER

    def test_invalid_passenger_name_blank(self):
        with pytest.raises(ValueError, match="cannot be blank"):
            PassengerDetails(name="   ", age=25)

    def test_invalid_passenger_age(self):
        with pytest.raises(ValueError):
            PassengerDetails(name="Sunita", age=0)
        with pytest.raises(ValueError):
            PassengerDetails(name="Sunita", age=130)

    def test_tatkal_passenger_count_limit(self):
        passengers = [
            PassengerDetails(name=f"Passenger {i}", age=20 + i)
            for i in range(5)
        ]
        with pytest.raises(ValueError, match="maximum of 4 passengers"):
            JourneyConfiguration(
                source_station="NDLS",
                destination_station="BCT",
                journey_date="2026-11-20",
                passengers=passengers,
            )


class TestTaskPreparationWorkflow:
    """Test the 12-point pre-flight preparation workflow."""

    @pytest.mark.asyncio
    async def test_full_12_point_preparation(self, client: TestClient):
        factory = get_session_factory()
        with factory() as db:
            task_svc = TaskService(db)
            task = task_svc.create_task(
                type("Req", (), {
                    "name": "Delhi to Mumbai Tatkal",
                    "task_type": "train_booking",
                    "description": "Autonomous booking task",
                    "configuration": {
                        "source_station": "NDLS - New Delhi",
                        "destination_station": "BCT - Mumbai Central",
                        "journey_date": "2026-12-15",
                        "travel_class": "3A",
                        "quota": "TATKAL",
                        "autonomous_agent": True,
                        "passengers": [
                            {"name": "Anil Kumar", "age": 32, "gender": "M"},
                            {"name": "Pooja Kumar", "age": 28, "gender": "F"},
                        ],
                    },
                })()
            )

            prep_svc = TaskPreparationService(db)
            report = await prep_svc.prepare_task(task.id)

            assert report.task_id == task.id
            assert report.overall_ready is True
            assert len(report.checks) == 12
            assert all(c.passed for c in report.checks if c.status == "PASSED")
            assert report.resolved_source_station["code"] == "NDLS"
            assert report.resolved_dest_station["code"] == "BCT"
            assert report.eligible_trains_count >= 1
            assert report.top_train is not None
            assert len(report.execution_plan) == 7
            assert "Final Payment Authorization" in report.requires_human_at_steps

            # Verify task status transitioned to READY
            db.refresh(task)
            assert task.status == TaskStatus.READY.value
            assert task.configuration.get("overall_ready") is True


class TestAutonomousAgentEndpoints:
    """Test API endpoints for preparation, scheduling, and execution."""

    def test_prepare_endpoint(self, client: TestClient):
        t_resp = client.post(
            "/api/v1/tasks",
            json={
                "name": "API Preparation Test",
                "task_type": "train_booking",
                "configuration": {
                    "source": "NDLS",
                    "destination": "BCT",
                    "travel_date": "2026-12-20",
                    "travel_class": "3A",
                    "passengers": [{"name": "Test User", "age": 30, "gender": "M"}],
                },
            },
        )
        assert t_resp.status_code == 201
        task_id = t_resp.json()["data"]["id"]

        prep_resp = client.post(f"/api/v1/tasks/{task_id}/prepare")
        assert prep_resp.status_code == 200
        data = prep_resp.json()["data"]
        assert data["task_id"] == task_id
        assert len(data["checks"]) == 12
        assert data["overall_ready"] is True

    def test_schedule_and_unschedule_endpoint(self, client: TestClient):
        t_resp = client.post(
            "/api/v1/tasks",
            json={
                "name": "Scheduling Test",
                "task_type": "train_booking",
                "configuration": {
                    "source": "NDLS",
                    "destination": "BCT",
                    "travel_date": "2026-12-25",
                    "travel_class": "3A",
                },
            },
        )
        task_id = t_resp.json()["data"]["id"]

        # Schedule
        sched_resp = client.post(f"/api/v1/tasks/{task_id}/schedule")
        assert sched_resp.status_code == 200
        timings = sched_resp.json()["data"]["timings"]
        assert timings["opening_time_ist"] == "10:00"  # AC 3A opens at 10:00 AM

        # Unschedule
        unsched_resp = client.post(f"/api/v1/tasks/{task_id}/unschedule")
        assert unsched_resp.status_code == 200


class TestAutonomousBookingPlannerAndBoundaries:
    """Test TatkalBookingAgentPlanner execution and human/payment boundaries."""

    @pytest.mark.asyncio
    async def test_planner_steps_and_payment_boundary(self):
        planner = TatkalBookingAgentPlanner()

        # Step 0: Should propose browser navigation
        req_0 = LLMRequest(
            planner_request=PlannerRequest(
                task_type="train_booking",
                current_step=0,
                task_configuration={"source": "NDLS", "destination": "BCT"},
            )
        )
        resp_0 = await planner.plan(req_0)
        p0 = resp_0.planner_response
        assert p0.action_type == ActionType.TOOL_ACTION
        assert p0.tool_name == "browser"
        assert p0.action_parameters["action_type"] == "navigate"

        # Step 4: CAPTCHA Checkpoint -> WAIT_FOR_HUMAN
        req_4 = LLMRequest(
            planner_request=PlannerRequest(
                task_type="train_booking",
                current_step=4,
                task_configuration={"source": "NDLS", "destination": "BCT"},
            )
        )
        resp_4 = await planner.plan(req_4)
        p4 = resp_4.planner_response
        assert p4.action_type == ActionType.WAIT_FOR_HUMAN
        assert "CAPTCHA" in p4.reason

        # Step 6: Payment Boundary Checkpoint -> WAIT_FOR_HUMAN with PAYMENT_STAGE_REACHED
        req_6 = LLMRequest(
            planner_request=PlannerRequest(
                task_type="train_booking",
                current_step=6,
                task_configuration={"source": "NDLS", "destination": "BCT"},
            )
        )
        resp_6 = await planner.plan(req_6)
        p6 = resp_6.planner_response
        assert p6.action_type == ActionType.WAIT_FOR_HUMAN
        assert "PAYMENT_STAGE_REACHED" in p6.reason

    @pytest.mark.asyncio
    async def test_autonomous_booking_execution_stops_at_payment_boundary(self, client: TestClient):
        """Verify end-to-end execution of autonomous booking stops before payment."""
        factory = get_session_factory()
        with factory() as db:
            task_svc = TaskService(db)
            task = task_svc.create_task(
                type("Req", (), {
                    "name": "Autonomous Payment Boundary Test",
                    "task_type": "train_booking",
                    "description": "Verifying payment boundary halt",
                    "configuration": {
                        "source": "NDLS",
                        "destination": "BCT",
                        "travel_date": "2026-12-20",
                        "travel_class": "3A",
                        "autonomous_agent": True,
                    },
                })()
            )

            run_svc = RunService(db)
            run = run_svc.create_run(task.id)

            # Execute run up to CAPTCHA step (step 4)
            updated_run = await run_svc.execute_run(run.id, max_steps=5)
            assert updated_run.status == "WAITING_FOR_HUMAN"

            # Check task status transitioned to AWAITING_HUMAN
            db.refresh(task)
            assert task.status == TaskStatus.AWAITING_HUMAN.value

            # Resume run from step 5 to payment boundary (step 6)
            resumed_run = run_svc.resume_run(run.id)
            assert resumed_run.status == "RUNNING"

            final_run = await run_svc.execute_run(run.id, max_steps=5)
            assert final_run.status == "WAITING_FOR_HUMAN"

            # Check task status transitioned to AWAITING_PAYMENT_APPROVAL
            db.refresh(task)
            assert task.status == TaskStatus.AWAITING_PAYMENT_APPROVAL.value
            assert "PAYMENT_STAGE_REACHED" in (final_run.error_summary or "")
