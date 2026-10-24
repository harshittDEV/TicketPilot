"""
Unit tests for EvidenceService and cryptographic artifact integrity verification (Phase 7).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from app.database.session import get_session_factory
from app.services.evidence_service import (
    EvidenceIntegrityError,
    EvidenceNotFoundError,
    EvidencePathTraversalError,
    EvidenceService,
)
from app.tools.artifacts import ArtifactSizeLimitExceededError


class TestEvidenceService:
    """Tests for artifact storage, SHA-256 calculation, and tamper detection."""

    def test_capture_evidence_atomic_and_checksum(self, tmp_path, tmp_db_url):
        """Captures evidence, writes atomically to disk, and records SHA-256 checksum in DB."""
        service = EvidenceService(base_dir=str(tmp_path), max_size_bytes=1024 * 1024)
        factory = get_session_factory()

        raw_payload = b'{"status": "SUCCESS", "step": "observation"}'
        expected_checksum = hashlib.sha256(raw_payload).hexdigest()

        with factory() as session:
            record = service.capture_evidence(
                session,
                data=raw_payload,
                evidence_type="DOM_SNAPSHOT",
                content_type="application/json",
                task_id="task-101",
                run_id="run-202",
                capture_source="observer",
                metadata={"url": "https://irctc.co.in/booking"},
            )
            evidence_id = record.id
            assert record.sha256_checksum == expected_checksum
            assert record.file_size_bytes == len(raw_payload)
            assert record.integrity_status == "VERIFIED"

        # Verify file exists on disk
        artifact_path = tmp_path / record.file_path
        assert artifact_path.exists()
        assert artifact_path.read_bytes() == raw_payload

    def test_verify_integrity_succeeds_for_untouched_file(self, tmp_path, tmp_db_url):
        """Integrity check passes and returns valid=True when disk file matches stored checksum."""
        service = EvidenceService(base_dir=str(tmp_path))
        factory = get_session_factory()
        data = b"image-png-binary-content-12345"

        with factory() as session:
            record = service.capture_evidence(
                session,
                data=data,
                evidence_type="SCREENSHOT",
                content_type="image/png",
            )
            ev_id = record.id

        with factory() as session:
            result = service.verify_integrity(session, ev_id)
            assert result["valid"] is True
            assert result["status"] == "VERIFIED"
            assert result["computed_checksum"] == result["stored_checksum"]

    def test_verify_integrity_detects_tampered_file(self, tmp_path, tmp_db_url):
        """Integrity check detects file alteration and updates status to TAMPERED."""
        service = EvidenceService(base_dir=str(tmp_path))
        factory = get_session_factory()
        data = b"original-unmodified-evidence"

        with factory() as session:
            record = service.capture_evidence(
                session,
                data=data,
                evidence_type="EXECUTION_SUMMARY",
                content_type="application/json",
            )
            ev_id = record.id
            rel_path = record.file_path

        # Tamper with the artifact on disk
        target_file = tmp_path / rel_path
        target_file.write_bytes(b"tampered-malicious-content")

        with factory() as session:
            result = service.verify_integrity(session, ev_id)
            assert result["valid"] is False
            assert result["status"] == "TAMPERED"
            assert result["computed_checksum"] != result["stored_checksum"]

            # Database record updated to TAMPERED
            updated_rec = service.get_evidence(session, ev_id)
            assert updated_rec.integrity_status == "TAMPERED"

    def test_verify_integrity_detects_missing_file(self, tmp_path, tmp_db_url):
        """Integrity check detects when artifact is missing from disk storage."""
        service = EvidenceService(base_dir=str(tmp_path))
        factory = get_session_factory()

        with factory() as session:
            record = service.capture_evidence(
                session,
                data=b"temporary-evidence",
                evidence_type="SCREENSHOT",
            )
            ev_id = record.id
            target_file = tmp_path / record.file_path

        # Delete artifact file from disk
        target_file.unlink()

        with factory() as session:
            result = service.verify_integrity(session, ev_id)
            assert result["valid"] is False
            assert result["status"] == "MISSING"
            assert result["computed_checksum"] is None

            updated_rec = service.get_evidence(session, ev_id)
            assert updated_rec.integrity_status == "MISSING"

    def test_size_limit_exceeded_rejected(self, tmp_path, tmp_db_url):
        """Rejects evidence payloads exceeding max_size_bytes."""
        service = EvidenceService(base_dir=str(tmp_path), max_size_bytes=100)
        factory = get_session_factory()

        oversized_data = b"x" * 101
        with factory() as session:
            with pytest.raises(ArtifactSizeLimitExceededError):
                service.capture_evidence(
                    session,
                    data=oversized_data,
                    evidence_type="SCREENSHOT",
                )

    def test_path_traversal_attempts_rejected(self, tmp_path):
        """Rejects paths containing '..' or trying to escape artifact base directory."""
        service = EvidenceService(base_dir=str(tmp_path))

        with pytest.raises(EvidencePathTraversalError):
            service._resolve_safe_path("../../../etc/passwd")

        with pytest.raises(EvidencePathTraversalError):
            service._resolve_safe_path("evidence/../../secret.txt")

    def test_read_evidence_data_by_id(self, tmp_path, tmp_db_url):
        """Safely reads binary data using controlled evidence_id resolution."""
        service = EvidenceService(base_dir=str(tmp_path))
        factory = get_session_factory()
        payload = b"raw-screenshot-pixels"

        with factory() as session:
            record = service.capture_evidence(
                session,
                data=payload,
                evidence_type="SCREENSHOT",
                content_type="image/png",
            )
            ev_id = record.id

        with factory() as session:
            rec, content = service.read_evidence_data(session, ev_id)
            assert rec.id == ev_id
            assert content == payload
