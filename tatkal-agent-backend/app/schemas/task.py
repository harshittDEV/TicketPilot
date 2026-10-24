"""
Pydantic v2 schemas for the Task API.

These schemas control what the client sends and what the server returns.
Internal fields (version, error internals) are not exposed unnecessarily.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request Schemas ──────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    """Schema for creating a new task."""
    name: Optional[str] = Field(
        None, max_length=255, description="Human-readable task name"
    )
    task_type: str = Field(
        ..., min_length=1, max_length=100, description="Task category (e.g. 'train_booking')"
    )
    description: Optional[str] = Field(
        None, max_length=2000, description="Optional task description"
    )
    configuration: dict[str, Any] = Field(
        default_factory=dict, description="Task-specific configuration (JSON)"
    )

    @field_validator("task_type")
    @classmethod
    def task_type_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("task_type must not be blank")
        return stripped


class TaskUpdateRequest(BaseModel):
    """
    Schema for updating permitted task metadata.

    Only explicitly allowed fields can be modified.
    Status, timestamps, version, and ID cannot be changed via this endpoint.
    """
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    configuration: Optional[dict[str, Any]] = None


class TaskTransitionRequest(BaseModel):
    """Schema for requesting a state transition."""
    target_status: str = Field(
        ..., description="The target lifecycle state to transition to"
    )
    reason: Optional[str] = Field(
        None, max_length=500, description="Optional reason for the transition"
    )


# ── Response Schemas ─────────────────────────────────────────────

class TaskResponse(BaseModel):
    """Public representation of a task."""
    model_config = {"from_attributes": True}

    id: str
    name: Optional[str] = None
    task_type: str
    status: str
    description: Optional[str] = None
    configuration: Optional[dict[str, Any]] = None
    current_step: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None
    version: int


class TaskStatusResponse(BaseModel):
    """Lightweight status view of a task."""
    model_config = {"from_attributes": True}

    id: str
    status: str
    current_step: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None


class TaskListMeta(BaseModel):
    """Pagination metadata for task listing."""
    total: int
    page: int
    page_size: int
    total_pages: int


class TaskListResponse(BaseModel):
    """Paginated list of tasks."""
    tasks: list[TaskResponse]
    meta: TaskListMeta


class TaskCancelResponse(BaseModel):
    """Response after cancelling a task."""
    id: str
    status: str
    cancelled_at: Optional[datetime] = None
    message: str = "Task cancelled successfully"
