"""
Integration endpoints for teammate modules (Phase 5).

Exposes routes for:
- Integration discovery and health reporting.
- Train candidate comparison and ranking (Member 4).
- Tatkal opening time calculation and run scheduling (Member 3).
- Security policy checks, secret vault management, and sensitive-data redaction (Member 4).
- Booking plan validation and safe execution handoff (Member 2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.integrations.contracts import (
    BookingContext,
    ScheduleRequest,
    SecurityCheckRequest,
    TrainQuery,
)
from app.integrations.registry import get_registry
from app.integrations.scheduler.calculator import calculate_tatkal_schedule
from app.integrations.security.redaction import redact_sensitive_data
from app.schemas.common import ApiResponse

router = APIRouter(tags=["Integrations"])


# ── Schemas ─────────────────────────────────────────────────────────

class TrainCompareRequest(BaseModel):
    source_station: str = Field(..., description="Origin station name or code")
    destination_station: str = Field(..., description="Destination station name or code")
    travel_date: str = Field(..., description="Travel date in YYYY-MM-DD format")
    travel_class: Optional[str] = Field(None, description="Optional class filter (e.g. SL, 3A, 2A)")
    quota: str = Field("TATKAL", description="Quota type (e.g. TATKAL, GENERAL)")


class CalculateScheduleRequest(BaseModel):
    journey_date: str = Field(..., description="Date train departs origin (YYYY-MM-DD)")
    travel_class: str = Field(..., description="Travel class code (e.g. SL, 3A, 2A)")
    reminder_minutes_before: int = Field(5, ge=0, le=120, description="Pre-alert lead time in minutes")


class CreateScheduleRequest(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    execute_at: datetime = Field(..., description="UTC time to execute the task")
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityCheckApiRequest(BaseModel):
    action: str = Field(..., description="The action being evaluated")
    actor: str = Field(..., description="Actor identifier requesting the action")
    resource: Optional[str] = Field(None, description="Target resource or secret reference")
    context: dict[str, Any] = Field(default_factory=dict)


class RedactApiRequest(BaseModel):
    payload: Any = Field(..., description="Data structure containing potential sensitive keys")


class BookingPlanApiRequest(BaseModel):
    task_id: str = Field(..., description="Associated task identifier")
    passenger_count: int = Field(..., ge=1, description="Number of passengers")
    journey_details: dict[str, Any] = Field(..., description="Train number, date, and passenger details")


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/integrations", response_model=ApiResponse[list[dict[str, Any]]])
async def list_integrations():
    """List all registered teammate integrations and their descriptors."""
    registry = get_registry()
    items = registry.list_integrations()
    return ApiResponse(
        data=items,
        message=f"Retrieved {len(items)} registered integration(s)",
    )


@router.get("/integrations/{name}/health", response_model=ApiResponse[dict[str, Any]])
async def check_integration_health(name: str):
    """Check health of a specific registered teammate integration."""
    registry = get_registry()
    if not registry.is_registered(name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration '{name}' is not registered",
        )
    health = await registry.check_integration_health(name)
    return ApiResponse(
        data=health,
        message=f"Integration '{name}' health check completed",
    )


@router.post("/trains/compare", response_model=ApiResponse[dict[str, Any]])
async def compare_trains(request: TrainCompareRequest):
    """
    Search and rank eligible train candidates based on fare, duration, and verified availability.
    """
    registry = get_registry()
    if not registry.is_registered("train_comparison"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Train comparison integration is not registered",
        )

    adapter = registry.get("train_comparison")
    query = TrainQuery(
        source_station=request.source_station,
        destination_station=request.destination_station,
        travel_date=request.travel_date,
        travel_class=request.travel_class,
        quota=request.quota,
    )

    try:
        result = await adapter.find_trains(query)
        return ApiResponse(
            data=result.model_dump(),
            message=result.message,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Train comparison query failed: {exc}",
        ) from exc


@router.post("/scheduler/calculate", response_model=ApiResponse[dict[str, Any]])
async def calculate_schedule_timings(request: CalculateScheduleRequest):
    """
    Calculate Tatkal opening date/time and pre-alert lead instants in IST and UTC.
    """
    try:
        timings = calculate_tatkal_schedule(
            journey_origin_departure_date=request.journey_date,
            travel_class=request.travel_class,
            reminder_minutes_before=request.reminder_minutes_before,
        )
        return ApiResponse(
            data=timings,
            message="Tatkal schedule timings calculated successfully",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/scheduler/schedule", response_model=ApiResponse[dict[str, Any]])
async def schedule_task_run(request: CreateScheduleRequest):
    """
    Schedule an execution run for a task at a specified UTC instant.
    """
    registry = get_registry()
    if not registry.is_registered("scheduler"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler integration is not registered",
        )

    adapter = registry.get("scheduler")
    sched_req = ScheduleRequest(
        task_id=request.task_id,
        execute_at=request.execute_at,
        metadata=request.metadata,
    )
    res = await adapter.schedule_run(sched_req)

    if res.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.message,
        )

    return ApiResponse(
        data=res.model_dump(),
        message=res.message,
    )


@router.delete("/scheduler/{schedule_id}", response_model=ApiResponse[dict[str, Any]])
async def cancel_scheduled_run(schedule_id: str):
    """Cancel a previously scheduled task run."""
    registry = get_registry()
    if not registry.is_registered("scheduler"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler integration is not registered",
        )

    adapter = registry.get("scheduler")
    res = await adapter.cancel_run(schedule_id)
    if res.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=res.message,
        )

    return ApiResponse(
        data=res.model_dump(),
        message=res.message,
    )


@router.post("/security/check", response_model=ApiResponse[dict[str, Any]])
async def check_security_authorization(request: SecurityCheckApiRequest):
    """
    Check whether a sensitive action is permitted according to security policy.
    """
    registry = get_registry()
    if not registry.is_registered("security"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security integration is not registered",
        )

    adapter = registry.get("security")
    sec_req = SecurityCheckRequest(
        action=request.action,
        actor=request.actor,
        resource=request.resource,
        context=request.context,
    )
    result = await adapter.check_authorization(sec_req)
    return ApiResponse(
        data=result.model_dump(),
        message=result.reason,
    )


@router.post("/security/redact", response_model=ApiResponse[Any])
async def redact_payload(request: RedactApiRequest):
    """
    Redact sensitive keys from an arbitrary JSON payload.
    """
    sanitized = redact_sensitive_data(request.payload)
    return ApiResponse(
        data=sanitized,
        message="Sensitive data redacted successfully",
    )


@router.post("/booking/plan", response_model=ApiResponse[dict[str, Any]])
async def create_booking_plan(request: BookingPlanApiRequest):
    """
    Validate passenger and journey context to create a safe booking execution plan.
    """
    registry = get_registry()
    if not registry.is_registered("booking_assistance"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking assistance integration is not registered",
        )

    adapter = registry.get("booking_assistance")
    context = BookingContext(
        task_id=request.task_id,
        passenger_count=request.passenger_count,
        journey_details=request.journey_details,
    )

    try:
        plan = adapter.generate_booking_plan(context)
        return ApiResponse(
            data=plan,
            message="Booking execution plan created with human approval checkpoints",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/booking/execute", response_model=ApiResponse[dict[str, Any]])
async def execute_booking_assistance(request: BookingPlanApiRequest):
    """
    Invoke booking assistance. Pauses before payment to enforce human authorization.
    """
    registry = get_registry()
    if not registry.is_registered("booking_assistance"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking assistance integration is not registered",
        )

    adapter = registry.get("booking_assistance")
    context = BookingContext(
        task_id=request.task_id,
        passenger_count=request.passenger_count,
        journey_details=request.journey_details,
    )

    result = await adapter.execute_booking(context)
    return ApiResponse(
        data=result.model_dump(),
        message=result.message,
    )


@router.get("/integrations/circuit-breakers", response_model=ApiResponse[dict[str, Any]])
async def list_circuit_breakers():
    """Retrieve operational state and metrics for all registered integration circuit breakers."""
    from app.agent.recovery.circuit_breaker import CircuitBreakerRegistry
    metrics = CircuitBreakerRegistry.get_all_metrics()
    return ApiResponse(
        data=metrics,
        message=f"Retrieved metrics for {len(metrics)} circuit breaker(s)",
    )
