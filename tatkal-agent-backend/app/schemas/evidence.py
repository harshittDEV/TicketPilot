"""
Evidence schemas for API responses and integrity checks (Phase 7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvidenceResponse(BaseModel):
    """Public representation of an EvidenceRecord."""
    id: str = Field(..., description="Unique evidence artifact identifier (UUID)")
    task_id: Optional[str] = Field(None, description="Associated task ID")
    run_id: Optional[str] = Field(None, description="Associated execution run ID")
    audit_event_id: Optional[str] = Field(None, description="Associated audit event ID")
    evidence_type: str = Field(..., description="Evidence type (e.g. SCREENSHOT, DOM_SNAPSHOT, EXECUTION_SUMMARY)")
    timestamp: datetime = Field(..., description="Creation timestamp (UTC)")
    file_path: str = Field(..., description="Controlled relative storage path")
    content_type: str = Field(..., description="MIME content type")
    file_size_bytes: int = Field(..., description="File size in bytes")
    sha256_checksum: str = Field(..., description="Cryptographic SHA-256 checksum")
    capture_source: str = Field(..., description="Originating tool or adapter")
    metadata_payload: Optional[dict[str, Any]] = Field(None, description="Sanitized descriptive metadata")
    integrity_status: str = Field(..., description="Integrity status: VERIFIED | TAMPERED | MISSING")

    model_config = {"from_attributes": True}


class EvidenceVerifyResponse(BaseModel):
    """Result of an evidence SHA-256 integrity verification check."""
    evidence_id: str
    status: str = Field(..., description="VERIFIED | TAMPERED | MISSING")
    valid: bool = Field(..., description="True if stored checksum matches disk file")
    stored_checksum: str
    computed_checksum: Optional[str] = None
    file_path: str
    file_size_bytes: int
    message: str


class EvidenceListMeta(BaseModel):
    """Pagination metadata for evidence listings."""
    total: int
    page: int
    page_size: int
    total_pages: int


class EvidenceListResponse(BaseModel):
    """Paginated collection of evidence records."""
    records: list[EvidenceResponse]
    meta: EvidenceListMeta
