"""
Scheduler integration adapter.

Implements the SchedulerIntegration protocol (contracts.py).
Integrates Member 3's Tatkal scheduling logic (scheduler.js) with the backend's
task lifecycle and execution runs.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.integrations.contracts import (
    ScheduleRequest,
    ScheduleResult,
    SchedulerIntegration,
)
from app.integrations.scheduler.calculator import (
    UTC,
    calculate_tatkal_schedule,
    get_opening_time_for_class,
)

logger = logging.getLogger(__name__)

# Maximum past delay in minutes eligible for recovery (from Member 3 scheduler.js)
MAX_RECOVERY_WINDOW_MINUTES = 10.0


@dataclass
class ScheduledJob:
    """Internal record of a scheduled execution run."""
    schedule_id: str
    task_id: str
    execute_at: datetime
    status: str  # "scheduled" | "cancelled" | "executed" | "recovered" | "expired"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None


class TatkalSchedulerAdapter:
    """
    Adapter implementing the SchedulerIntegration protocol.

    Features:
    - Calculates Tatkal opening and reminder times based on train class and journey date.
    - Manages scheduled jobs with duplicate prevention.
    - Recovers missed reminders if within 10 minutes past opening.
    - Rejects expired schedules older than 10 minutes in the past.
    - Conforms strictly to SchedulerIntegration (schedule_run, cancel_run).
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._sent_alert_ids: set[str] = set()

    async def schedule_run(self, request: ScheduleRequest) -> ScheduleResult:
        """
        Schedule a task execution run.

        Validates execution time, checks duplicate status, and evaluates recovery eligibility.
        """
        now_utc = datetime.now(timezone.utc)
        exec_at = request.execute_at
        if exec_at.tzinfo is None:
            exec_at = exec_at.replace(tzinfo=timezone.utc)
        else:
            exec_at = exec_at.astimezone(timezone.utc)

        # Check for duplicate prevention key in metadata
        dedup_key = request.metadata.get("dedup_key") or f"{request.task_id}_{exec_at.isoformat()}"
        if dedup_key in self._sent_alert_ids:
            logger.warning("Duplicate schedule prevented: %s", dedup_key)
            return ScheduleResult(
                schedule_id="",
                status="failed",
                message=f"Duplicate scheduling prevented: alert '{dedup_key}' already processed",
            )

        # Evaluate time difference
        diff_seconds = (exec_at - now_utc).total_seconds()

        schedule_id = f"sched_{uuid.uuid4().hex[:12]}"

        if diff_seconds > 0:
            status = "scheduled"
            msg = f"Task '{request.task_id}' scheduled for execution at {exec_at.isoformat()} (UTC)"
        elif diff_seconds >= -(MAX_RECOVERY_WINDOW_MINUTES * 60):
            # Recovery window: <= 10 minutes in the past
            status = "recovered"
            self._sent_alert_ids.add(dedup_key)
            msg = (
                f"Recovered missed schedule for task '{request.task_id}' "
                f"({abs(diff_seconds):.1f}s past window, within {MAX_RECOVERY_WINDOW_MINUTES}m recovery limit)"
            )
            logger.info("RECOVERING MISSED REMINDER: %s", dedup_key)
        else:
            # Expired: more than 10 minutes late
            status = "expired"
            self._sent_alert_ids.add(dedup_key)
            msg = (
                f"Schedule for task '{request.task_id}' is expired ({abs(diff_seconds)/60:.1f}m late) "
                "and was not replayed"
            )
            logger.warning("MISSED/EXPIRED: %s; not replayed", dedup_key)
            return ScheduleResult(
                schedule_id=schedule_id,
                status="failed",
                message=msg,
            )

        job = ScheduledJob(
            schedule_id=schedule_id,
            task_id=request.task_id,
            execute_at=exec_at,
            status=status,
            metadata=request.metadata,
        )
        self._jobs[schedule_id] = job
        logger.info("Schedule created [%s]: %s", schedule_id, msg)

        return ScheduleResult(
            schedule_id=schedule_id,
            status=status,
            message=msg,
        )

    async def cancel_run(self, schedule_id: str) -> ScheduleResult:
        """
        Cancel a previously scheduled run.
        """
        job = self._jobs.get(schedule_id)
        if not job:
            return ScheduleResult(
                schedule_id=schedule_id,
                status="failed",
                message=f"Schedule '{schedule_id}' not found",
            )

        if job.status == "cancelled":
            return ScheduleResult(
                schedule_id=schedule_id,
                status="cancelled",
                message=f"Schedule '{schedule_id}' is already cancelled",
            )

        job.status = "cancelled"
        logger.info("Schedule '%s' for task '%s' cancelled", schedule_id, job.task_id)
        return ScheduleResult(
            schedule_id=schedule_id,
            status="cancelled",
            message=f"Schedule '{schedule_id}' has been cancelled",
        )

    def calculate_opening(
        self,
        journey_date: str,
        travel_class: str,
        reminder_minutes_before: int = 5,
    ) -> dict[str, Any]:
        """Convenience method to calculate Tatkal timings for a journey."""
        return calculate_tatkal_schedule(
            journey_origin_departure_date=journey_date,
            travel_class=travel_class,
            reminder_minutes_before=reminder_minutes_before,
        )

    def get_schedule(self, schedule_id: str) -> Optional[dict[str, Any]]:
        """Retrieve details of a scheduled job."""
        job = self._jobs.get(schedule_id)
        if not job:
            return None
        return {
            "schedule_id": job.schedule_id,
            "task_id": job.task_id,
            "execute_at": job.execute_at.isoformat(),
            "status": job.status,
            "metadata": job.metadata,
            "created_at": job.created_at.isoformat(),
        }

    def list_schedules(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """List all scheduled jobs, optionally filtered by status."""
        results: list[dict[str, Any]] = []
        for job in self._jobs.values():
            if status is None or job.status == status:
                results.append({
                    "schedule_id": job.schedule_id,
                    "task_id": job.task_id,
                    "execute_at": job.execute_at.isoformat(),
                    "status": job.status,
                    "metadata": job.metadata,
                })
        return results

    async def health_check(self) -> bool:
        """Return True if scheduler adapter is operational."""
        return True

    def get_metadata(self) -> dict[str, Any]:
        """Return metadata describing scheduler capabilities."""
        return {
            "name": "scheduler",
            "version": "1.0.0",
            "description": "IRCTC Tatkal booking opening time calculation and task run scheduling",
            "active_schedules_count": len([j for j in self._jobs.values() if j.status == "scheduled"]),
            "timezone": "Asia/Kolkata (IST = UTC+05:30)",
            "supported_classes": ["2A", "3A", "CC", "EC", "3E", "SL", "FC", "2S"],
            "recovery_window_minutes": MAX_RECOVERY_WINDOW_MINUTES,
        }
