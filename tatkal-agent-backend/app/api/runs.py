"""
Execution Run API endpoints.

Routes are mounted under ``/api/v1``.
Business logic is delegated to ``RunService``.

Creating a run does NOT silently execute an entire agent workflow
inside the HTTP request.  The orchestrator requires an explicit
execution entry point (Phase 4+).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from typing import Optional

from app.database.session import get_db
from app.schemas.run import (
    RunCreateRequest,
    RunExecuteRequest,
    RunListMeta,
    RunListResponse,
    RunResponse,
    RunStatusResponse,
    RunTransitionRequest,
)
from app.services.run_service import RunService

router = APIRouter(tags=["Runs"])


def _get_run_service(db: Session = Depends(get_db)) -> RunService:
    """FastAPI dependency that provides a RunService for the current request."""
    return RunService(db)


# ── POST /tasks/{task_id}/runs ───────────────────────────────────

@router.post(
    "/tasks/{task_id}/runs",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new execution run for a task",
)
def create_run(
    task_id: str,
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """
    Create a run in the PENDING state.

    Validates that the task exists, is not in a terminal state, and
    has no other active run.  Does NOT start execution.
    """
    run = svc.create_run(task_id)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "success": True,
            "data": RunResponse.model_validate(run).model_dump(mode="json"),
            "message": "Execution run created successfully",
        },
    )


# ── GET /tasks/{task_id}/runs ────────────────────────────────────

@router.get(
    "/tasks/{task_id}/runs",
    response_model=dict,
    summary="List execution runs for a task",
)
def list_runs(
    task_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """Return paginated runs for a task (newest first)."""
    runs, meta = svc.list_runs(task_id, page=page, page_size=page_size)
    payload = RunListResponse(
        runs=[RunResponse.model_validate(r) for r in runs],
        meta=meta,
    )
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": payload.model_dump(mode="json"),
            "message": "Runs retrieved successfully",
        },
    )


# ── GET /runs/{run_id} ──────────────────────────────────────────

@router.get(
    "/runs/{run_id}",
    response_model=dict,
    summary="Retrieve an execution run by ID",
)
def get_run(
    run_id: str,
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """Return the full public representation of an execution run."""
    run = svc.get_run(run_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": RunResponse.model_validate(run).model_dump(mode="json"),
            "message": "Run retrieved successfully",
        },
    )


# ── POST /runs/{run_id}/pause ────────────────────────────────────

@router.post(
    "/runs/{run_id}/pause",
    response_model=dict,
    summary="Pause a running execution run",
)
def pause_run(
    run_id: str,
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """Pause a RUNNING run at the next safe checkpoint."""
    run = svc.pause_run(run_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": RunResponse.model_validate(run).model_dump(mode="json"),
            "message": "Run paused successfully",
        },
    )


# ── POST /runs/{run_id}/resume ───────────────────────────────────

@router.post(
    "/runs/{run_id}/resume",
    response_model=dict,
    summary="Resume a paused or waiting-for-human run",
)
def resume_run(
    run_id: str,
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """Resume a PAUSED or WAITING_FOR_HUMAN run."""
    run = svc.resume_run(run_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": RunResponse.model_validate(run).model_dump(mode="json"),
            "message": "Run resumed successfully",
        },
    )


# ── POST /runs/{run_id}/cancel ───────────────────────────────────

@router.post(
    "/runs/{run_id}/cancel",
    response_model=dict,
    summary="Cancel an execution run",
)
def cancel_run(
    run_id: str,
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """Cancel a run if its current state permits cancellation."""
    run = svc.cancel_run(run_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": RunResponse.model_validate(run).model_dump(mode="json"),
            "message": "Run cancelled successfully",
        },
    )


# ── POST /runs/{run_id}/transition ───────────────────────────────

@router.post(
    "/runs/{run_id}/transition",
    response_model=dict,
    summary="Transition an execution run to a new state",
    description="Validate and transition an execution run through the centralized state machine.",
)
def transition_run(
    run_id: str,
    request: RunTransitionRequest,
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """Transition a run via the centralized state machine."""
    run = svc.transition_run(
        run_id,
        request.target_status,
        error_code=request.error_code,
        error_summary=request.error_summary,
        current_step=request.current_step,
        steps_completed=request.steps_completed,
    )
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": RunResponse.model_validate(run).model_dump(mode="json"),
            "message": f"Run transitioned to {run.status}",
        },
    )


# ── POST /runs/{run_id}/execute ──────────────────────────────────

@router.post(
    "/runs/{run_id}/execute",
    response_model=dict,
    summary="Execute an execution run through the agent orchestrator",
    description="Executes the full sense-plan-act-verify loop for the run, updating status and capturing evidence.",
)
async def execute_run(
    run_id: str,
    request: Optional[RunExecuteRequest] = None,
    svc: RunService = Depends(_get_run_service),
) -> JSONResponse:
    """Execute the run through the agent orchestrator."""
    max_steps = request.max_steps if request else None
    timeout = request.timeout_seconds if request else None
    run = await svc.execute_run(
        run_id,
        max_steps=max_steps,
        timeout_seconds=timeout,
    )
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": RunResponse.model_validate(run).model_dump(mode="json"),
            "message": f"Run execution finished with status {run.status}",
        },
    )
