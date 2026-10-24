"""
Audit schemas for API responses and queries (Phase 7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    """Public representation of an AuditEvent."""
    id: str = Field(..., description="Unique event identifier (UUID)")
    task_id: Optional[str] = Field(None, description="Associated task ID")
    run_id: Optional[str] = Field(None, description="Associated execution run ID")
    correlation_id: Optional[str] = Field(None, description="Trace correlation ID")
    event_type: str = Field(..., description="Specific event type (e.g. task.created, tool.execution.success)")
    event_category: str = Field(..., description="Category: TASK | RUN | TOOL | SKILL | RECOVERY | SECURITY | EVIDENCE")
    timestamp: datetime = Field(..., description="Event timestamp (UTC)")
    outcome: str = Field(..., description="Event outcome: SUCCESS | FAILURE | WARNING | PENDING")
    source: str = Field(..., description="Originating subsystem or module")
    tool_or_skill_name: Optional[str] = Field(None, description="Target tool or skill name")
    error_code: Optional[str] = Field(None, description="Standardized error code")
    event_metadata: Optional[dict[str, Any]] = Field(None, description="Sanitized structured metadata")
    evidence_references: Optional[list[str]] = Field(None, description="Linked evidence artifact IDs")
    schema_version: int = Field(1, description="Event schema version")

    model_config = {"from_attributes": True}


class AuditListMeta(BaseModel):
    """Pagination metadata for audit queries."""
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditEventListResponse(BaseModel):
    """Paginated collection of audit events."""
    events: list[AuditEventResponse]
    meta: AuditListMeta
