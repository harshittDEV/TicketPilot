"""
Audit API endpoints (Phase 7).

Mounted under ``/api/v1/audit``.
Exposes structured, paginated audit events with task, run, and category filtering.
"""

from __future__ import annotations

from datetime import datetime
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.audit import AuditEventListResponse, AuditEventResponse, AuditListMeta
from app.schemas.common import ApiResponse
from app.services.audit_service import AuditEventNotFoundError, get_audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/events", response_model=ApiResponse[AuditEventListResponse])
def list_audit_events(
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    run_id: Optional[str] = Query(None, description="Filter by execution run ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    event_category: Optional[str] = Query(None, description="Filter by category (TASK, RUN, TOOL, SKILL, RECOVERY)"),
    start_time: Optional[datetime] = Query(None, description="Filter events after UTC timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter events before UTC timestamp"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List paginated audit events with optional filtering."""
    service = get_audit_service()
    events, total = service.list_events(
        db,
        task_id=task_id,
        run_id=run_id,
        event_type=event_type,
        event_category=event_category,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    meta = AuditListMeta(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    event_responses = [AuditEventResponse.model_validate(e) for e in events]
    return ApiResponse(
        data=AuditEventListResponse(events=event_responses, meta=meta),
        message=f"Retrieved {len(events)} audit event(s)",
    )


@router.get("/events/{event_id}", response_model=ApiResponse[AuditEventResponse])
def get_audit_event(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve an audit event by its unique ID."""
    service = get_audit_service()
    try:
        event = service.get_event(db, event_id)
        return ApiResponse(
            data=AuditEventResponse.model_validate(event),
            message="Audit event retrieved successfully",
        )
    except AuditEventNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/tasks/{task_id}/events", response_model=ApiResponse[AuditEventListResponse])
def get_task_audit_events(
    task_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Retrieve all audit events associated with a specific task."""
    return list_audit_events(
        task_id=task_id,
        run_id=None,
        event_type=None,
        event_category=None,
        start_time=None,
        end_time=None,
        page=page,
        page_size=page_size,
        db=db,
    )


@router.get("/runs/{run_id}/events", response_model=ApiResponse[AuditEventListResponse])
def get_run_audit_events(
    run_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """Retrieve all audit events associated with a specific execution run."""
    return list_audit_events(
        task_id=None,
        run_id=run_id,
        event_type=None,
        event_category=None,
        start_time=None,
        end_time=None,
        page=page,
        page_size=page_size,
        db=db,
    )
