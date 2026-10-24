"""
Railway Data Endpoints (Phase 9).

Exposes routes for:
- Provider status, capabilities, and cache metrics
- Station search and details
- Trains running between stations with schedule/fare info
- Stop-by-stop train schedules
- Live running status observations
- PNR status inquiries
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.integrations.railway.contracts import (
    LiveRunningStatus,
    PnrStatus,
    ProviderStatusResponse,
    Station,
    TrainBetweenStations,
    TrainSchedule,
)
from app.integrations.railway.service import get_railway_service
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/railway", tags=["Railway Data"])


@router.get("/providers/status", response_model=ApiResponse[ProviderStatusResponse])
async def get_provider_status():
    """Report railway data provider status, operating mode, and cache metrics."""
    service = get_railway_service()
    status_data = service.get_provider_status()
    return ApiResponse(
        data=status_data,
        message="Railway provider status and capabilities retrieved",
    )


@router.get("/stations", response_model=ApiResponse[list[Station]])
async def search_stations_endpoint(
    q: str = Query("", description="Station code, name, city, or state keyword"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of stations to return"),
):
    """Search verified Indian Railways stations by code, name, city, or state."""
    service = get_railway_service()
    results = await service.search_stations(q, limit=limit)
    return ApiResponse(
        data=results,
        message=f"Found {len(results)} matching station(s)",
    )


@router.get("/stations/{code}", response_model=ApiResponse[Station])
async def get_station_by_code_endpoint(code: str):
    """Retrieve details for a specific station code."""
    service = get_railway_service()
    station = service.get_station_details(code)
    if not station:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station code '{code.upper()}' not found in directory",
        )
    return ApiResponse(
        data=station,
        message=f"Station {station.code} retrieved successfully",
    )


@router.get("/trains/between", response_model=ApiResponse[list[TrainBetweenStations]])
async def get_trains_between_endpoint(
    from_station: str = Query(..., description="Origin station code or name (e.g. NDLS)"),
    to_station: str = Query(..., description="Destination station code or name (e.g. BCT)"),
    date: str = Query(..., description="Journey date YYYY-MM-DD"),
    travel_class: Optional[str] = Query(None, description="Optional class filter (SL, 3A, 2A, 1A, CC)"),
):
    """
    Search authentic trains running between origin and destination stations.
    Never fabricates fake train results if no match exists.
    """
    if from_station.strip().upper() == to_station.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Origin and destination stations must be different",
        )

    service = get_railway_service()
    trains = await service.get_trains_between(
        source=from_station,
        destination=to_station,
        journey_date=date,
        travel_class=travel_class,
    )
    return ApiResponse(
        data=trains,
        message=f"Retrieved {len(trains)} train(s) between {from_station} and {to_station}",
    )


@router.get("/trains/{train_number}/schedule", response_model=ApiResponse[TrainSchedule])
async def get_train_schedule_endpoint(train_number: str):
    """Retrieve detailed stop-by-stop timetable schedule for a train."""
    service = get_railway_service()
    schedule = await service.get_train_schedule(train_number)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timetable for train '{train_number}' not found",
        )
    return ApiResponse(
        data=schedule,
        message=f"Schedule for train {train_number} ({schedule.train_name}) retrieved",
    )


@router.get("/trains/{train_number}/live", response_model=ApiResponse[LiveRunningStatus])
async def get_live_running_status_endpoint(
    train_number: str,
    date: str = Query(..., description="Journey start date YYYY-MM-DD"),
):
    """
    Retrieve live running telemetry. If live GPS feed is unconfigured,
    returns truthful status without fabricating fake delays or coordinates.
    """
    service = get_railway_service()
    live_status = await service.get_live_running_status(train_number, date)
    return ApiResponse(
        data=live_status,
        message=live_status.status_message,
    )


@router.get("/pnr/{pnr_number}", response_model=ApiResponse[PnrStatus])
async def get_pnr_status_endpoint(pnr_number: str):
    """
    Retrieve PNR status if supported. Returns truthful unsupported response
    when credentials are not configured, protecting passenger privacy.
    """
    clean_pnr = pnr_number.replace("-", "").strip()
    if len(clean_pnr) != 10 or not clean_pnr.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PNR must be a 10-digit number",
        )

    service = get_railway_service()
    pnr = await service.get_pnr_status(clean_pnr)
    return ApiResponse(
        data=pnr,
        message=pnr.message,
    )
