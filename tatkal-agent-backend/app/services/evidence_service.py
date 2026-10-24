"""
Evidence service — manages structured evidence artifacts and integrity checks (Phase 7).

Features:
- Collision-resistant file naming using UUIDs and timestamps.
- Path traversal protection (all paths strictly bounded within artifact_dir).
- Atomic file writes using temporary files and atomic renames.
- SHA-256 checksum computation and tamper detection.
- Database persistence of EvidenceRecord metadata.
- Safe controlled artifact resolution and retrieval.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.security.redaction import redact_sensitive_data
from app.models.audit import EvidenceRecord
from app.tools.artifacts import ArtifactError, ArtifactSizeLimitExceededError

logger = logging.getLogger(__name__)


class EvidenceError(ArtifactError):
    """Base error for evidence operations."""


class EvidenceNotFoundError(EvidenceError):
    """Raised when an evidence record or artifact file cannot be found."""


class EvidenceIntegrityError(EvidenceError):
    """Raised when an artifact checksum does not match its record."""


class EvidencePathTraversalError(EvidenceError):
    """Raised when an unsafe path traversal attempt is detected."""


class EvidenceService:
    """
    Manages capturing, persisting, verifying, and reading evidence artifacts.
    """

    def __init__(self, base_dir: Optional[str] = None, max_size_bytes: Optional[int] = None) -> None:
        settings = get_settings()
        self._base_dir = Path(base_dir or settings.artifact_dir).resolve()
        self._max_size_bytes = max_size_bytes or settings.max_artifact_size_bytes
        self._evidence_dir = self._base_dir / "evidence"
        self._evidence_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """
        Safely resolve a relative artifact path, rejecting directory traversal attempts.
        """
        clean = relative_path.replace("\\", "/").lstrip("/")
        # Reject explicit traversal sequences
        parts = clean.split("/")
        if ".." in parts or "." in parts:
            raise EvidencePathTraversalError(f"Directory traversal detected in path: '{relative_path}'")

        resolved = (self._base_dir / clean).resolve()
        try:
            resolved.relative_to(self._base_dir)
        except ValueError:
            raise EvidencePathTraversalError(f"Path escapes artifact base directory: '{relative_path}'")

        return resolved

    def capture_evidence(
        self,
        db: Session,
        *,
        data: bytes,
        evidence_type: str,
        content_type: str = "application/octet-stream",
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        audit_event_id: Optional[str] = None,
        capture_source: str = "agent_system",
        metadata: Optional[dict[str, Any]] = None,
        subfolder: str = "evidence",
        file_extension: Optional[str] = None,
    ) -> EvidenceRecord:
        """
        Atomically write an evidence artifact to disk and persist its metadata record.

        Args:
            db: SQLAlchemy session.
            data: Raw binary payload.
            evidence_type: Classification (e.g. SCREENSHOT, DOM_SNAPSHOT, EXECUTION_SUMMARY).
            content_type: MIME content type (e.g. image/png, application/json).
            task_id: Optional parent task ID.
            run_id: Optional parent execution run ID.
            audit_event_id: Optional associated audit event ID.
            capture_source: Originating component or tool name.
            metadata: Structured descriptive context (sanitized before storage).
            subfolder: Subdirectory inside artifact_dir (default: 'evidence').
            file_extension: Optional explicit file extension (e.g. 'png', 'json').

        Returns:
            Created EvidenceRecord entity.
        """
        if len(data) > self._max_size_bytes:
            raise ArtifactSizeLimitExceededError(
                f"Evidence size ({len(data)} bytes) exceeds limit ({self._max_size_bytes} bytes)"
            )

        # Determine extension from content_type if not given
        if not file_extension:
            if "png" in content_type:
                file_extension = "png"
            elif "json" in content_type:
                file_extension = "json"
            elif "html" in content_type:
                file_extension = "html"
            elif "text" in content_type:
                file_extension = "txt"
            else:
                file_extension = "bin"

        file_extension = file_extension.lstrip(".")
        unique_id = uuid.uuid4().hex
        timestamp_int = int(time.time())
        type_prefix = evidence_type.lower().replace(" ", "_")
        filename = f"{type_prefix}_{timestamp_int}_{unique_id[:12]}.{file_extension}"

        # Target directory
        target_dir = self._base_dir / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        final_file_path = target_dir / filename

        # Compute SHA-256 checksum
        hasher = hashlib.sha256(data)
        checksum = hasher.hexdigest()

        # Atomic write: write to temp file first, then atomically rename
        temp_fd, temp_path_str = tempfile.mkstemp(dir=str(target_dir), prefix="tmp_ev_", suffix=".tmp")
        temp_path = Path(temp_path_str)
        try:
            with os.fdopen(temp_fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            temp_path.replace(final_file_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

        rel_path = f"{subfolder}/{filename}"
        sanitized_meta = redact_sensitive_data(metadata) if metadata else None

        record = EvidenceRecord(
            id=str(uuid.uuid4()),
            task_id=task_id,
            run_id=run_id,
            audit_event_id=audit_event_id,
            evidence_type=evidence_type.upper(),
            file_path=rel_path,
            content_type=content_type,
            file_size_bytes=len(data),
            sha256_checksum=checksum,
            capture_source=capture_source,
            metadata_payload=sanitized_meta,
            integrity_status="VERIFIED",
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(
            "Evidence captured: id=%s type=%s size=%d path=%s checksum=%s",
            record.id,
            record.evidence_type,
            record.file_size_bytes,
            record.file_path,
            record.sha256_checksum[:12],
        )
        return record

    def get_evidence(self, db: Session, evidence_id: str) -> EvidenceRecord:
        """Retrieve evidence record by ID or raise EvidenceNotFoundError."""
        record = db.get(EvidenceRecord, evidence_id)
        if not record:
            raise EvidenceNotFoundError(f"Evidence record '{evidence_id}' not found")
        return record

    def read_evidence_data(self, db: Session, evidence_id: str) -> tuple[EvidenceRecord, bytes]:
        """
        Read binary content for an evidence record safely.

        Returns (record, binary_content).
        """
        record = self.get_evidence(db, evidence_id)
        safe_path = self._resolve_safe_path(record.file_path)

        if not safe_path.exists() or not safe_path.is_file():
            raise EvidenceNotFoundError(f"Artifact file for evidence '{evidence_id}' is missing from disk")

        content = safe_path.read_bytes()
        return record, content

    def verify_integrity(self, db: Session, evidence_id: str) -> dict[str, Any]:
        """
        Verify the SHA-256 integrity of an evidence artifact on disk.

        Detects missing files and checksum mismatches (tamper detection).
        Updates `integrity_status` on the database record.
        """
        record = self.get_evidence(db, evidence_id)
        safe_path = self._resolve_safe_path(record.file_path)

        if not safe_path.exists() or not safe_path.is_file():
            record.integrity_status = "MISSING"
            db.commit()
            return {
                "evidence_id": record.id,
                "status": "MISSING",
                "valid": False,
                "stored_checksum": record.sha256_checksum,
                "computed_checksum": None,
                "file_path": record.file_path,
                "file_size_bytes": record.file_size_bytes,
                "message": "Artifact file is missing from filesystem storage",
            }

        file_bytes = safe_path.read_bytes()
        computed_checksum = hashlib.sha256(file_bytes).hexdigest()

        if computed_checksum == record.sha256_checksum:
            record.integrity_status = "VERIFIED"
            valid = True
            msg = "Artifact integrity verified successfully"
        else:
            record.integrity_status = "TAMPERED"
            valid = False
            msg = "Checksum mismatch: artifact content has been altered or corrupted"

        db.commit()
        return {
            "evidence_id": record.id,
            "status": record.integrity_status,
            "valid": valid,
            "stored_checksum": record.sha256_checksum,
            "computed_checksum": computed_checksum,
            "file_path": record.file_path,
            "file_size_bytes": len(file_bytes),
            "message": msg,
        }

    def list_evidence(
        self,
        db: Session,
        *,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        evidence_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvidenceRecord], int]:
        """List evidence records with pagination and optional filters."""
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        stmt = select(EvidenceRecord)
        if task_id:
            stmt = stmt.where(EvidenceRecord.task_id == task_id)
        if run_id:
            stmt = stmt.where(EvidenceRecord.run_id == run_id)
        if evidence_type:
            stmt = stmt.where(EvidenceRecord.evidence_type == evidence_type.upper())

        # Total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        # Pagination & deterministic ordering
        stmt = stmt.order_by(EvidenceRecord.timestamp.desc(), EvidenceRecord.id.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list(db.scalars(stmt).all())

        return items, total


# Singleton instance helper
_evidence_service: EvidenceService | None = None


def get_evidence_service() -> EvidenceService:
    """Return the global EvidenceService instance."""
    global _evidence_service
    if _evidence_service is None:
        _evidence_service = EvidenceService()
    return _evidence_service


def reset_evidence_service() -> None:
    """Reset the global EvidenceService instance (useful for test isolation)."""
    global _evidence_service
    _evidence_service = None
