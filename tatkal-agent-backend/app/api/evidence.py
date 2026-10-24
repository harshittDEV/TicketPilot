"""
Evidence API endpoints (Phase 7).

Mounted under ``/api/v1/evidence``.
Exposes evidence metadata listing, SHA-256 tamper verification, and safe controlled artifact downloads.
"""

from __future__ import annotations

import math
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.evidence import (
    EvidenceListMeta,
    EvidenceListResponse,
    EvidenceResponse,
    EvidenceVerifyResponse,
)
from app.services.evidence_service import (
    EvidenceNotFoundError,
    EvidencePathTraversalError,
    get_evidence_service,
)

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.get("", response_model=ApiResponse[EvidenceListResponse])
def list_evidence(
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    run_id: Optional[str] = Query(None, description="Filter by execution run ID"),
    evidence_type: Optional[str] = Query(None, description="Filter by evidence type (e.g. SCREENSHOT)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List paginated evidence artifact records with optional filtering."""
    service = get_evidence_service()
    records, total = service.list_evidence(
        db,
        task_id=task_id,
        run_id=run_id,
        evidence_type=evidence_type,
        page=page,
        page_size=page_size,
    )

    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    meta = EvidenceListMeta(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    evidence_responses = [EvidenceResponse.model_validate(r) for r in records]
    return ApiResponse(
        data=EvidenceListResponse(records=evidence_responses, meta=meta),
        message=f"Retrieved {len(records)} evidence record(s)",
    )


@router.get("/{evidence_id}", response_model=ApiResponse[EvidenceResponse])
def get_evidence_metadata(
    evidence_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve metadata for an evidence artifact by ID."""
    service = get_evidence_service()
    try:
        record = service.get_evidence(db, evidence_id)
        return ApiResponse(
            data=EvidenceResponse.model_validate(record),
            message="Evidence metadata retrieved successfully",
        )
    except EvidenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{evidence_id}/verify", response_model=ApiResponse[EvidenceVerifyResponse])
def verify_evidence_integrity(
    evidence_id: str,
    db: Session = Depends(get_db),
):
    """
    Verify the SHA-256 cryptographic integrity of a stored evidence artifact.

    Detects file tampering, corruption, or missing storage files.
    """
    service = get_evidence_service()
    try:
        result = service.verify_integrity(db, evidence_id)
        return ApiResponse(
            data=EvidenceVerifyResponse(**result),
            message=result["message"],
        )
    except EvidenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/{evidence_id}/download")
def download_evidence_artifact(
    evidence_id: str,
    db: Session = Depends(get_db),
):
    """
    Download or stream an evidence artifact file safely.

    Access is strictly controlled by unique evidence_id; arbitrary filesystem paths
    cannot be accessed or traversed.
    """
    service = get_evidence_service()
    try:
        record, content = service.read_evidence_data(db, evidence_id)
        filename = os.path.basename(record.file_path)
        return Response(
            content=content,
            media_type=record.content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Evidence-Checksum": record.sha256_checksum,
            },
        )
    except (EvidenceNotFoundError, EvidencePathTraversalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
