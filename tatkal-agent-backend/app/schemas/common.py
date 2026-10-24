"""
Common Pydantic schemas for consistent API responses.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error payload returned to API clients."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")


class ApiResponse(BaseModel, Generic[T]):
    """Standard envelope for all successful API responses."""
    success: bool = True
    data: Optional[T] = None
    message: str = "Operation completed"


class ApiErrorResponse(BaseModel):
    """Standard envelope for all error API responses."""
    success: bool = False
    error: ErrorDetail


class HealthResponse(BaseModel):
    """Health-check response payload."""
    status: str = Field(..., description="Overall application status: ok | degraded | unhealthy")
    api_version: str
    database: str = Field(..., description="Database connectivity: connected | disconnected")
