"""
Scheduled Execution Engine for Autonomous Booking Tasks.

Conforms to Section 7:
- Responsible for identifying when a task is eligible to start and requesting
  execution through the agent orchestration service.
- Enforces unique execution policies, survives restarts, recovers scheduled tasks,
  handles missed windows explicitly, and respects cancellation/pauses.
- Records scheduler-trigger events to the audit log.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_session_factory
from app.models.task import Task
from app.services.audit_service import get_audit_service
from app.services.run_service import RunService
from app.services.task_service import TaskService
from app.services.task_state_machine import TaskStatus

logger = logging.getLogger(__name__)

# Singleton engine instance
_scheduler_engine: Optional[AgentSchedulerEngine] = None


class AgentSchedulerEngine:
    """
    Background scheduler engine that monitors scheduled booking tasks
    and launches agent execution runs when opening windows arrive.
    """

    def __init__(self, check_interval_seconds: float = 10.0) -> None:
        self._interval = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_triggers: set[str] = set()

    async def start(self) -> None:
        """Start the background scheduler evaluation loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("AgentSchedulerEngine started (interval=%.1fs)", self._interval)

    async def stop(self) -> None:
        """Stop the background scheduler evaluation loop cleanly."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AgentSchedulerEngine stopped")

    async def _run_loop(self) -> None:
        """Periodic loop to evaluate scheduled tasks."""
        while self._running:
            try:
                await self.evaluate_scheduled_tasks()
            except Exception as exc:
                logger.error("Error in scheduler evaluation loop: %s", exc, exc_info=True)
            await asyncio.sleep(self._interval)

    async def evaluate_scheduled_tasks(self) -> list[dict[str, Any]]:
        """
        Evaluate all tasks in the database to check if any scheduled opening window
        has arrived and is eligible for execution.
        """
        results: list[dict[str, Any]] = []
        now_utc = datetime.now(timezone.utc)
        factory = get_session_factory()

        with factory() as db:
            # Query active eligible tasks (READY or CREATED)
            stmt = select(Task).where(
                Task.status.in_([TaskStatus.READY.value, TaskStatus.CREATED.value])
            )
            tasks = db.scalars(stmt).all()

            for task in tasks:
                cfg = task.configuration or {}
                scheduled_str = cfg.get("scheduled_opening_utc")
                if not scheduled_str:
                    continue

                if task.id in self._active_triggers:
                    continue

                try:
                    scheduled_dt = datetime.fromisoformat(scheduled_str)
                except ValueError:
                    continue

                # Check if opening window has arrived
                if now_utc >= scheduled_dt:
                    # Check for missed window (e.g. more than 30 minutes past opening)
                    window_expiry = scheduled_dt + timedelta(minutes=30)
                    if now_utc > window_expiry:
                        logger.warning(
                            "Task '%s' missed its booking window (scheduled=%s, now=%s)",
                            task.id, scheduled_str, now_utc.isoformat(),
                        )
                        get_audit_service().record_event(
                            event_type="scheduler.window_missed",
                            event_category="TASK",
                            outcome="WARNING",
                            source="scheduler_engine",
                            task_id=task.id,
                            metadata={"scheduled_for": scheduled_str, "evaluated_at": now_utc.isoformat()},
                            db=db,
                        )
                        # Mark task as expired / missed window in config
                        updated_cfg = dict(cfg)
                        updated_cfg["window_missed"] = True
                        task.configuration = updated_cfg
                        db.commit()
                        results.append({"task_id": task.id, "status": "MISSED_WINDOW"})
                        continue

                    # Trigger task execution
                    self._active_triggers.add(task.id)
                    try:
                        logger.info("Triggering scheduled agent execution for task '%s'", task.id)
                        run_svc = RunService(db)
                        run = run_svc.create_run(task.id)

                        get_audit_service().record_event(
                            event_type="scheduler.task_triggered",
                            event_category="TASK",
                            outcome="SUCCESS",
                            source="scheduler_engine",
                            task_id=task.id,
                            run_id=run.id,
                            metadata={
                                "scheduled_opening_utc": scheduled_str,
                                "triggered_at": now_utc.isoformat(),
                            },
                            db=db,
                        )

                        # Launch execution
                        asyncio.create_task(self._execute_run_async(run.id))
                        results.append({"task_id": task.id, "run_id": run.id, "status": "TRIGGERED"})
                    except Exception as exc:
                        logger.error("Failed to trigger scheduled run for task '%s': %s", task.id, exc)
                        results.append({"task_id": task.id, "status": "TRIGGER_FAILED", "error": str(exc)})
                    finally:
                        self._active_triggers.discard(task.id)

        return results

    async def _execute_run_async(self, run_id: str) -> None:
        """Asynchronously execute the run through the agent orchestrator."""
        factory = get_session_factory()
        with factory() as db:
            run_svc = RunService(db)
            try:
                await run_svc.execute_run(run_id)
            except Exception as exc:
                logger.error("Async execution run '%s' failed: %s", run_id, exc)


def get_scheduler_engine() -> AgentSchedulerEngine:
    """Return the global AgentSchedulerEngine singleton."""
    global _scheduler_engine
    if _scheduler_engine is None:
        _scheduler_engine = AgentSchedulerEngine()
    return _scheduler_engine
