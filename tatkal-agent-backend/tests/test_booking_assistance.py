"""
Tests for Booking Assistance adapter and safety boundaries.
"""

import pytest

from app.integrations.booking.adapter import BookingAssistanceAdapter
from app.integrations.contracts import BookingContext


class TestBookingAssistanceAdapter:
    """Verify booking assistance plan generation and safety boundaries."""

    def test_generate_booking_plan_success(self):
        adapter = BookingAssistanceAdapter()
        context = BookingContext(
            task_id="task_book_1",
            passenger_count=2,
            journey_details={
                "train_number": "12002",
                "travel_date": "2026-11-20",
                "travel_class": "CC",
                "passengers": [
                    {"passengerName": "Alice", "age": 30},
                    {"passengerName": "Bob", "age": 32},
                ],
            },
        )
        plan = adapter.generate_booking_plan(context)
        assert plan["task_id"] == "task_book_1"
        assert plan["train_number"] == "12002"
        assert plan["passenger_count"] == 2
        assert len(plan["steps"]) == 5

        # Checkpoints for CAPTCHA and payment require human
        human_steps = [s for s in plan["steps"] if s["requires_human"]]
        assert len(human_steps) == 2
        assert any("captcha" in s["name"] for s in human_steps)
        assert any("payment" in s["name"] for s in human_steps)

        # Passenger name must be redacted in stored plan
        safe_passengers = plan["sanitized_journey_details"]["passengers"]
        assert safe_passengers[0]["passengerName"] == "[REDACTED]"

    def test_generate_plan_missing_train_number_raises(self):
        adapter = BookingAssistanceAdapter()
        context = BookingContext(
            task_id="task_fail",
            passenger_count=1,
            journey_details={"travel_date": "2026-11-20"},
        )
        with pytest.raises(ValueError, match="train_number"):
            adapter.generate_booking_plan(context)

    def test_generate_plan_missing_travel_date_raises(self):
        adapter = BookingAssistanceAdapter()
        context = BookingContext(
            task_id="task_fail",
            passenger_count=1,
            journey_details={"train_number": "12001"},
        )
        with pytest.raises(ValueError, match="travel_date"):
            adapter.generate_booking_plan(context)

    @pytest.mark.asyncio
    async def test_execute_booking_pauses_for_human_intervention(self):
        adapter = BookingAssistanceAdapter()
        context = BookingContext(
            task_id="task_exec",
            passenger_count=1,
            journey_details={
                "train_number": "12002",
                "travel_date": "2026-11-20",
                "travel_class": "2S",
            },
        )
        result = await adapter.execute_booking(context)

        # Booking cannot be marked successful automatically without human payment authorization
        assert result.success is False
        assert "AWAITING_HUMAN_INTERVENTION" == result.evidence["status"]
        assert result.evidence["requires_human"] is True
        assert "payment_authorization" in result.evidence["human_checkpoints"]

    @pytest.mark.asyncio
    async def test_execute_booking_invalid_context_returns_failure(self):
        adapter = BookingAssistanceAdapter()
        context = BookingContext(
            task_id="task_bad",
            passenger_count=1,
            journey_details={},  # missing required fields
        )
        result = await adapter.execute_booking(context)
        assert result.success is False
        assert "validation failed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_health_check_and_metadata(self):
        adapter = BookingAssistanceAdapter()
        assert await adapter.health_check() is True
        meta = adapter.get_metadata()
        assert meta["name"] == "booking_assistance"
        assert meta["live_booking_enabled"] is False
