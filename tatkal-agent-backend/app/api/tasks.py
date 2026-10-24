"""
Task API endpoints.

All routes are mounted under ``/api/v1/tasks``.
Business logic is delegated to ``TaskService``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.task import (
    TaskCancelResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatusResponse,
    TaskTransitionRequest,
    TaskUpdateRequest,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _get_task_service(db: Session = Depends(get_db)) -> TaskService:
    """FastAPI dependency that provides a TaskService for the current request."""
    return TaskService(db)


# ── POST /tasks ──────────────────────────────────────────────────

@router.post(
    "",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
)
def create_task(
    request: TaskCreateRequest,
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Create a task in the CREATED state. The server generates the ID and timestamps."""
    task = svc.create_task(request)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "success": True,
            "data": TaskResponse.model_validate(task).model_dump(mode="json"),
            "message": "Task created successfully",
        },
    )


# ── GET /tasks ───────────────────────────────────────────────────

@router.get(
    "",
    response_model=dict,
    summary="List tasks with pagination and optional filters",
)
def list_tasks(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    task_type: str | None = Query(None, description="Filter by task type"),
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Return a paginated, filtered list of tasks (newest first)."""
    tasks, meta = svc.list_tasks(
        status=status_filter, task_type=task_type, page=page, page_size=page_size
    )
    payload = TaskListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        meta=meta,
    )
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": payload.model_dump(mode="json"),
            "message": "Tasks retrieved successfully",
        },
    )


# ── GET /tasks/{task_id} ─────────────────────────────────────────

@router.get(
    "/{task_id}",
    response_model=dict,
    summary="Retrieve a task by ID",
)
def get_task(
    task_id: str,
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Return the full public representation of a task."""
    task = svc.get_task(task_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": TaskResponse.model_validate(task).model_dump(mode="json"),
            "message": "Task retrieved successfully",
        },
    )


# ── GET /tasks/{task_id}/status ──────────────────────────────────

@router.get(
    "/{task_id}/status",
    response_model=dict,
    summary="Retrieve task status and lifecycle timestamps",
)
def get_task_status(
    task_id: str,
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Return a lightweight status view of a task."""
    task = svc.get_task(task_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": TaskStatusResponse.model_validate(task).model_dump(mode="json"),
            "message": "Task status retrieved successfully",
        },
    )


# ── POST /tasks/{task_id}/transition ─────────────────────────────

@router.post(
    "/{task_id}/transition",
    response_model=dict,
    summary="Transition a task to a new state (internal orchestration)",
    description=(
        "**Internal orchestration interface.** Validates the transition "
        "through the centralised state machine. Must be restricted before "
        "production deployment."
    ),
)
def transition_task(
    task_id: str,
    request: TaskTransitionRequest,
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Validate and apply a state transition on a task."""
    task = svc.transition_task(task_id, request.target_status)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": TaskResponse.model_validate(task).model_dump(mode="json"),
            "message": f"Task transitioned to {task.status}",
        },
    )


# ── POST /tasks/{task_id}/cancel ─────────────────────────────────

@router.post(
    "/{task_id}/cancel",
    response_model=dict,
    summary="Cancel a task",
)
def cancel_task(
    task_id: str,
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Cancel a task if its current state permits cancellation."""
    task = svc.cancel_task(task_id)
    payload = TaskCancelResponse(
        id=task.id,
        status=task.status,
        cancelled_at=task.cancelled_at,
        message="Task cancelled successfully",
    )
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": payload.model_dump(mode="json"),
            "message": "Task cancelled successfully",
        },
    )


# ── PATCH /tasks/{task_id} ───────────────────────────────────────

@router.patch(
    "/{task_id}",
    response_model=dict,
    summary="Update task metadata",
    description=(
        "Update permitted metadata fields (name, description, configuration). "
        "Status, timestamps, version, and ID cannot be changed via this endpoint."
    ),
)
def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Update permitted metadata fields on a task."""
    task = svc.update_task(task_id, request)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": TaskResponse.model_validate(task).model_dump(mode="json"),
            "message": "Task updated successfully",
        },
    )


# ── POST /tasks/{task_id}/prepare ────────────────────────────────

@router.post(
    "/{task_id}/prepare",
    response_model=dict,
    summary="Execute pre-flight preparation workflow for a task",
    description=(
        "Runs the 12-point pre-flight preparation workflow: validates journey and passenger details, "
        "resolves stations, fetches timetables, verifies data freshness, checks credentials, "
        "identifies human prerequisites, verifies Tatkal opening window, and builds the execution plan."
    ),
)
async def prepare_task(
    task_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Execute the 12-point pre-flight preparation workflow."""
    from app.services.preparation_service import TaskPreparationService
    prep_svc = TaskPreparationService(db)
    report = await prep_svc.prepare_task(task_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": report.model_dump(),
            "message": "Pre-flight preparation completed successfully",
        },
    )


# ── POST /tasks/{task_id}/schedule ───────────────────────────────

@router.post(
    "/{task_id}/schedule",
    response_model=dict,
    summary="Schedule task for automated execution at Tatkal opening window",
)
async def schedule_task(
    task_id: str,
    db: Session = Depends(get_db),
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """
    Compute Tatkal opening window and schedule task for autonomous trigger.
    """
    from app.integrations.scheduler.calculator import calculate_tatkal_schedule
    from app.services.audit_service import get_audit_service

    task = svc.get_task(task_id)
    cfg = task.configuration or {}

    journey_date = cfg.get("journey_date") or cfg.get("travel_date")
    travel_class = cfg.get("travel_class") or "3A"
    reminder_mins = cfg.get("reminder_minutes_before", 15)

    if not journey_date:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": {"code": "MISSING_DATE", "message": "Task configuration requires journey_date (YYYY-MM-DD)"}},
        )

    timings = calculate_tatkal_schedule(
        journey_origin_departure_date=journey_date,
        travel_class=travel_class,
        reminder_minutes_before=reminder_mins,
    )

    updated_cfg = dict(cfg)
    updated_cfg["scheduled_opening_utc"] = timings["opening_datetime_utc"]
    updated_cfg["scheduled_opening_ist"] = timings["opening_datetime_ist"]
    updated_cfg["pre_alert_datetime_utc"] = timings["pre_alert_datetime_utc"]
    updated_cfg["window_missed"] = False

    task.configuration = updated_cfg
    db.commit()

    get_audit_service().record_event(
        event_type="scheduler.task_scheduled",
        event_category="TASK",
        outcome="SUCCESS",
        source="tasks_api",
        task_id=task.id,
        metadata={
            "scheduled_opening_ist": timings["opening_datetime_ist"],
            "scheduled_opening_utc": timings["opening_datetime_utc"],
        },
        db=db,
    )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "task_id": task.id,
                "timings": timings,
                "scheduled_execution_time": timings["opening_datetime_ist"],
                "status": task.status,
            },
            "message": f"Task successfully scheduled for Tatkal opening at {timings['opening_time_ist']} IST",
        },
    )


# ── POST /tasks/{task_id}/unschedule ─────────────────────────────

@router.post(
    "/{task_id}/unschedule",
    response_model=dict,
    summary="Unschedule task and remove scheduled opening triggers",
)
def unschedule_task(
    task_id: str,
    db: Session = Depends(get_db),
    svc: TaskService = Depends(_get_task_service),
) -> JSONResponse:
    """Remove scheduling triggers from task."""
    task = svc.get_task(task_id)
    cfg = dict(task.configuration or {})
    cfg.pop("scheduled_opening_utc", None)
    cfg.pop("scheduled_opening_ist", None)
    cfg.pop("pre_alert_datetime_utc", None)
    task.configuration = cfg
    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {"task_id": task.id},
            "message": "Task unscheduled successfully",
        },
    )

