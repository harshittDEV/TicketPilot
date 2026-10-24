"""
Tests for Tatkal scheduler calculation and integration adapter (Member 3).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.integrations.contracts import ScheduleRequest
from app.integrations.scheduler.adapter import TatkalSchedulerAdapter
from app.integrations.scheduler.calculator import (
    calculate_tatkal_schedule,
    get_opening_time_for_class,
)


class TestTatkalOpeningCalculator:
    """Verify IRCTC Tatkal opening rules and timezone calculations."""

    def test_ac_classes_open_at_10am_ist(self):
        for class_code in ("2A", "3A", "CC", "EC", "3E"):
            assert get_opening_time_for_class(class_code) == "10:00"

    def test_non_ac_classes_open_at_11am_ist(self):
        for class_code in ("SL", "FC", "2S"):
            assert get_opening_time_for_class(class_code) == "11:00"

    def test_unsupported_class_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported Tatkal travel class"):
            get_opening_time_for_class("FIRST_CLASS")

    def test_opening_date_is_one_day_prior(self):
        res = calculate_tatkal_schedule("2026-11-15", "SL", reminder_minutes_before=5)
        assert res["journey_origin_departure_date"] == "2026-11-15"
        assert res["opening_date"] == "2026-11-14"
        assert res["opening_time_ist"] == "11:00"

    def test_ist_to_utc_conversion(self):
        res = calculate_tatkal_schedule("2026-11-15", "3A", reminder_minutes_before=10)
        # 10:00 AM IST on 2026-11-14 = 04:30 AM UTC on 2026-11-14
        assert "2026-11-14T10:00:00+05:30" in res["opening_datetime_ist"]
        assert "2026-11-14T04:30:00+00:00" in res["opening_datetime_utc"]

        # Pre-alert: 10 mins before = 09:50 AM IST = 04:20 AM UTC
        assert "2026-11-14T09:50:00+05:30" in res["pre_alert_datetime_ist"]
        assert "2026-11-14T04:20:00+00:00" in res["pre_alert_datetime_utc"]

    def test_invalid_date_format_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid journey date format"):
            calculate_tatkal_schedule("15-11-2026", "SL")


class TestTatkalSchedulerAdapter:
    """Verify scheduler adapter operations, recovery, and duplicate prevention."""

    @pytest.mark.asyncio
    async def test_schedule_future_run_success(self):
        adapter = TatkalSchedulerAdapter()
        future_time = datetime.now(timezone.utc) + timedelta(hours=2)

        req = ScheduleRequest(
            task_id="task_123",
            execute_at=future_time,
            metadata={"journey": "Delhi-Mumbai"},
        )
        res = await adapter.schedule_run(req)

        assert res.status == "scheduled"
        assert res.schedule_id.startswith("sched_")
        assert "task_123" in res.message

        job = adapter.get_schedule(res.schedule_id)
        assert job is not None
        assert job["task_id"] == "task_123"

    @pytest.mark.asyncio
    async def test_schedule_recovery_within_10_minutes(self):
        adapter = TatkalSchedulerAdapter()
        # 3 minutes in the past -> within 10 min recovery window
        past_time = datetime.now(timezone.utc) - timedelta(minutes=3)

        req = ScheduleRequest(
            task_id="task_recover",
            execute_at=past_time,
        )
        res = await adapter.schedule_run(req)

        assert res.status == "recovered"
        assert "Recovered missed schedule" in res.message

    @pytest.mark.asyncio
    async def test_schedule_expired_past_10_minutes(self):
        adapter = TatkalSchedulerAdapter()
        # 15 minutes in the past -> expired
        past_time = datetime.now(timezone.utc) - timedelta(minutes=15)

        req = ScheduleRequest(
            task_id="task_expired",
            execute_at=past_time,
        )
        res = await adapter.schedule_run(req)

        assert res.status == "failed"
        assert "expired" in res.message.lower()

    @pytest.mark.asyncio
    async def test_duplicate_schedule_prevention(self):
        adapter = TatkalSchedulerAdapter()
        past_time = datetime.now(timezone.utc) - timedelta(minutes=2)

        req = ScheduleRequest(
            task_id="task_dup",
            execute_at=past_time,
            metadata={"dedup_key": "unique_alert_key"},
        )
        res1 = await adapter.schedule_run(req)
        assert res1.status == "recovered"

        # Re-submitting the exact same dedup_key must be prevented
        res2 = await adapter.schedule_run(req)
        assert res2.status == "failed"
        assert "duplicate" in res2.message.lower()

    @pytest.mark.asyncio
    async def test_cancel_schedule(self):
        adapter = TatkalSchedulerAdapter()
        future_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        req = ScheduleRequest(task_id="task_cancel", execute_at=future_time)
        res = await adapter.schedule_run(req)

        cancel_res = await adapter.cancel_run(res.schedule_id)
        assert cancel_res.status == "cancelled"

        # Repeated cancel returns already cancelled
        cancel_res2 = await adapter.cancel_run(res.schedule_id)
        assert cancel_res2.status == "cancelled"
        assert "already cancelled" in cancel_res2.message

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_schedule(self):
        adapter = TatkalSchedulerAdapter()
        res = await adapter.cancel_run("nonexistent_id")
        assert res.status == "failed"
        assert "not found" in res.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_and_metadata(self):
        adapter = TatkalSchedulerAdapter()
        assert await adapter.health_check() is True
        meta = adapter.get_metadata()
        assert meta["name"] == "scheduler"
        assert "SL" in meta["supported_classes"]
