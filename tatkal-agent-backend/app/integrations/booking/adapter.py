"""
Booking assistance integration adapter.

Implements the BookingAssistanceIntegration protocol (contracts.py).
Enforces safety boundaries:
- Distinguishes booking plan generation from actual booking execution.
- Validates passenger details and journey criteria.
- Prohibits unattended ticket purchase and automated payment approval.
- Emits structured results with human-intervention checkpoints for CAPTCHA and payment.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.integrations.contracts import (
    BookingAssistanceIntegration,
    BookingContext,
    BookingResult,
)
from app.integrations.security.redaction import redact_sensitive_data

logger = logging.getLogger(__name__)


class BookingAssistanceAdapter:
    """
    Adapter implementing the BookingAssistanceIntegration protocol.

    Provides pre-booking validation, booking plan generation, and safe execution handoffs
    while strictly disallowing automated live purchasing or payment.
    """

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    def generate_booking_plan(self, context: BookingContext) -> dict[str, Any]:
        """
        Validate booking parameters and generate an execution plan with safety checkpoints.

        Raises:
            ValueError: If passenger count is invalid or journey details are missing.
        """
        if context.passenger_count < 1:
            raise ValueError(f"Invalid passenger count {context.passenger_count}; must be >= 1")

        jd = context.journey_details
        train_num = jd.get("train_number") or jd.get("trainNumber")
        if not train_num:
            raise ValueError("Missing 'train_number' in journey_details")

        travel_date = jd.get("travel_date") or jd.get("journeyDate")
        if not travel_date:
            raise ValueError("Missing 'travel_date' in journey_details")

        travel_class = jd.get("travel_class") or jd.get("class") or "SL"

        # Redact passenger names / IDs for plan storage
        safe_jd = redact_sensitive_data(jd)

        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        return {
            "plan_id": plan_id,
            "task_id": context.task_id,
            "train_number": str(train_num),
            "travel_date": str(travel_date),
            "travel_class": str(travel_class),
            "passenger_count": context.passenger_count,
            "steps": [
                {
                    "step_id": 1,
                    "name": "login_and_navigate",
                    "requires_human": False,
                    "description": "Navigate to booking portal and verify session",
                },
                {
                    "step_id": 2,
                    "name": "train_selection",
                    "requires_human": False,
                    "description": f"Select train {train_num} and class {travel_class}",
                },
                {
                    "step_id": 3,
                    "name": "passenger_entry",
                    "requires_human": False,
                    "description": f"Populate {context.passenger_count} passenger record(s)",
                },
                {
                    "step_id": 4,
                    "name": "captcha_verification",
                    "requires_human": True,
                    "description": "Human operator must verify/solve the CAPTCHA barrier",
                },
                {
                    "step_id": 5,
                    "name": "payment_authorization",
                    "requires_human": True,
                    "description": "Human operator must authorize and complete final payment",
                },
            ],
            "sanitized_journey_details": safe_jd,
        }

    async def execute_booking(self, context: BookingContext) -> BookingResult:
        """
        Invoke booking assistance with a validated task context.

        Phase 5 Safety Enforcement:
        Unattended live payment and live booking are disallowed. This method
        generates the validated plan and returns a structured outcome identifying
        that human approval is required for payment and confirmation.
        """
        logger.info(
            "Booking assistance invoked for task '%s' (passengers=%d)",
            context.task_id,
            context.passenger_count,
        )

        try:
            plan = self.generate_booking_plan(context)
        except ValueError as exc:
            logger.warning("Booking validation failed for task '%s': %s", context.task_id, exc)
            return BookingResult(
                task_id=context.task_id,
                success=False,
                message=f"Booking validation failed: {exc}",
                evidence={"error": str(exc)},
            )

        # In Phase 5, automated live payment is strictly disabled
        return BookingResult(
            task_id=context.task_id,
            success=False,  # Intentionally False: booking is not completed until human approves payment
            message=(
                "Booking plan validated successfully. Live booking paused: "
                "Human intervention is required for CAPTCHA challenge and payment authorization."
            ),
            evidence={
                "plan_id": plan["plan_id"],
                "train_number": plan["train_number"],
                "passenger_count": plan["passenger_count"],
                "requires_human": True,
                "human_checkpoints": ["captcha_verification", "payment_authorization"],
                "status": "AWAITING_HUMAN_INTERVENTION",
            },
        )

    async def health_check(self) -> bool:
        """Return True if booking assistance adapter is operational."""
        return True

    def get_metadata(self) -> dict[str, Any]:
        """Return metadata describing booking assistance capabilities."""
        return {
            "name": "booking_assistance",
            "version": "1.0.0",
            "description": "Booking plan generator and human-assisted checkout coordinator",
            "live_booking_enabled": False,
            "dry_run": self.dry_run,
            "safety_boundaries": [
                "No automated payment execution",
                "No anti-bot evasion",
                "Mandatory human handoff for CAPTCHA and payment",
            ],
        }
