"""
Health-check endpoint.

Reports application status, API version, and database connectivity.
Never exposes credentials, file paths, or internal configuration.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.database.session import check_database_connection
from app.schemas.common import ApiResponse, HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=ApiResponse[HealthResponse],
    summary="Application health check",
    responses={
        200: {"description": "All systems operational"},
        503: {"description": "One or more systems degraded"},
    },
)
async def health_check() -> JSONResponse:
    """
    Check application health.

    Returns:
        - **status**: ``ok`` when all systems operational, ``degraded`` otherwise.
        - **api_version**: Current API version.
        - **database**: ``connected`` or ``disconnected``.
    """
    settings = get_settings()
    db_ok = check_database_connection()

    health = HealthResponse(
        status="ok" if db_ok else "degraded",
        api_version=settings.api_version,
        database="connected" if db_ok else "disconnected",
    )

    http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=http_status,
        content={
            "success": db_ok,
            "data": health.model_dump(),
            "message": "All systems operational" if db_ok else "Database connectivity issue",
        },
    )


@router.get(
    "/health/liveness",
    summary="Process liveness probe",
    description="Returns 200 OK if the application server is up and responsive.",
)
async def liveness_check() -> JSONResponse:
    """Lightweight process liveness probe for orchestrators/monitors."""
    settings = get_settings()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "data": {
                "status": "alive",
                "api_version": settings.api_version,
            },
            "message": "Backend process is active",
        },
    )


@router.get(
    "/health/readiness",
    summary="Service readiness probe",
    description="Returns 200 OK if database, storage paths, and registry are ready to accept traffic.",
    responses={
        200: {"description": "Service is ready to handle requests"},
        503: {"description": "One or more critical subsystems are not ready"},
    },
)
async def readiness_check() -> JSONResponse:
    """Comprehensive readiness probe verifying DB, storage directories, and registry."""
    import os
    from app.integrations.registry import get_registry

    settings = get_settings()
    db_ok = check_database_connection()
    dirs_ok = os.path.isdir(settings.data_dir) and os.path.isdir(settings.artifact_dir)

    registry = get_registry()
    tools_ready = registry.is_tool_registered("browser") or registry.is_registered("browser")

    is_ready = db_ok and dirs_ok and tools_ready
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    subsystems = {
        "database": "connected" if db_ok else "disconnected",
        "storage": "ready" if dirs_ok else "missing_directories",
        "tool_registry": "ready" if tools_ready else "uninitialized",
    }

    return JSONResponse(
        status_code=status_code,
        content={
            "success": is_ready,
            "data": {
                "status": "ready" if is_ready else "not_ready",
                "subsystems": subsystems,
                "api_version": settings.api_version,
            },
            "message": "Backend is ready for requests" if is_ready else "Subsystems not ready",
        },
    )
