"""
Pydantic v2 schemas for the Execution Run API.

Controls what the client sends and what the server returns for run
operations.  Internal fields (version internals) are not exposed
unnecessarily.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────

class RunCreateRequest(BaseModel):
    """Schema for creating a new execution run."""
    # Run creation is primarily driven by the system (orchestrator or API).
    # No task-specific config here — that lives on the Task.
    pass


class RunTransitionRequest(BaseModel):
    """Request schema for manually / internally transitioning a run."""
    target_status: str = Field(..., description="Target lifecycle state for the run")
    error_code: Optional[str] = Field(None, description="Error code for failure states")
    error_summary: Optional[str] = Field(None, description="Human-readable error summary")
    current_step: Optional[str] = Field(None, description="Updated current step name")
    steps_completed: Optional[int] = Field(None, description="Updated completed steps count")


class RunExecuteRequest(BaseModel):
    """Optional configuration parameters when invoking run execution."""
    max_steps: Optional[int] = Field(None, ge=1, le=500, description="Maximum execution steps before stopping")
    timeout_seconds: Optional[float] = Field(None, ge=1.0, le=3600.0, description="Overall execution deadline in seconds")


# ── Response Schemas ─────────────────────────────────────────────

class RunResponse(BaseModel):
    """Public representation of an execution run."""
    model_config = {"from_attributes": True}

    id: str
    task_id: str
    status: str
    current_step: Optional[str] = None
    steps_completed: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None
    version: int


class RunStatusResponse(BaseModel):
    """Lightweight status view of a run."""
    model_config = {"from_attributes": True}

    id: str
    task_id: str
    status: str
    current_step: Optional[str] = None
    steps_completed: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None


class RunListMeta(BaseModel):
    """Pagination metadata for run listing."""
    total: int
    page: int
    page_size: int
    total_pages: int


class RunListResponse(BaseModel):
    """Paginated list of runs."""
    runs: list[RunResponse]
    meta: RunListMeta
