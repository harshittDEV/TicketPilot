"""
Artifact management for agent observations and tool execution.

Handles collision-resistant storage, size bounding, and safe reference
resolution for screenshots and other run artifacts.

REDACTION NOTICE:
    Automated visual redaction (e.g. OCR-based or pixel masking of passwords,
    CVVs, or OTPs) is NOT implemented in Phase 4. Screenshots reflect the raw
    rendered state. Sensitive credentials must not be typed or displayed
    during automated capture.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Optional
import uuid

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ArtifactError(Exception):
    """Base error for artifact management."""


class ArtifactSizeLimitExceededError(ArtifactError):
    """Raised when an artifact exceeds the allowed byte limit."""


class ArtifactNotFoundError(ArtifactError):
    """Raised when an artifact reference cannot be resolved."""


class ArtifactManager:
    """
    Manages filesystem storage and retrieval of execution artifacts.

    Features:
        - Collision-resistant file naming using UUIDs and timestamps.
        - Directory traversal protection.
        - Enforcement of maximum artifact file sizes.
        - Safe predictable URI references (e.g. ``artifact://screenshots/<filename>``).
    """

    def __init__(
        self,
        base_dir: Optional[str] = None,
        max_size_bytes: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self._base_dir = Path(base_dir or settings.artifact_dir).resolve()
        self._screenshots_dir = self._base_dir / "screenshots"
        self._max_size_bytes = max_size_bytes or settings.max_artifact_size_bytes

        # Ensure directory structure exists
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def screenshots_dir(self) -> Path:
        return self._screenshots_dir

    def save_screenshot(
        self,
        data: bytes,
        *,
        format: str = "png",
        prefix: str = "screen",
        run_id: Optional[str] = None,
    ) -> str:
        """
        Save binary screenshot data and return an artifact reference.

        Args:
            data: Raw image bytes.
            format: Image format extension (default 'png').
            prefix: Filename prefix.
            run_id: Optional run ID for correlation.

        Returns:
            A predictable artifact reference, e.g. ``artifact://screenshots/screen_abc123.png``.

        Raises:
            ArtifactSizeLimitExceededError: If *data* exceeds configured size limit.
        """
        if len(data) > self._max_size_bytes:
            raise ArtifactSizeLimitExceededError(
                f"Screenshot size ({len(data)} bytes) exceeds limit "
                f"({self._max_size_bytes} bytes)"
            )

        unique_id = uuid.uuid4().hex[:12]
        timestamp = int(time.time())
        run_tag = f"_{run_id[:8]}" if run_id else ""
        filename = f"{prefix}{run_tag}_{timestamp}_{unique_id}.{format}"

        file_path = self._screenshots_dir / filename
        file_path.write_bytes(data)
        logger.debug("Saved screenshot artifact: %s (%d bytes)", filename, len(data))

        return f"artifact://screenshots/{filename}"

    def resolve_reference(self, artifact_ref: str) -> Path:
        """
        Safely resolve an artifact reference to an absolute filesystem Path.

        Guards against directory traversal attacks.

        Args:
            artifact_ref: e.g. ``artifact://screenshots/abc.png`` or ``screenshots/abc.png``.

        Returns:
            Resolved absolute Path.

        Raises:
            ArtifactNotFoundError: If reference format is invalid or file doesn't exist.
        """
        prefix = "artifact://"
        clean_ref = artifact_ref[len(prefix):] if artifact_ref.startswith(prefix) else artifact_ref

        # Prevent traversal
        resolved = (self._base_dir / clean_ref).resolve()
        try:
            resolved.relative_to(self._base_dir)
        except ValueError:
            raise ArtifactNotFoundError(f"Invalid artifact reference: '{artifact_ref}'")

        if not resolved.exists() or not resolved.is_file():
            raise ArtifactNotFoundError(f"Artifact not found: '{artifact_ref}'")

        return resolved

    def read_artifact(self, artifact_ref: str) -> bytes:
        """Read and return binary artifact content."""
        path = self.resolve_reference(artifact_ref)
        return path.read_bytes()

    def list_artifacts(self, subfolder: str = "screenshots") -> list[dict[str, Any]]:
        """List metadata for stored artifacts in the given subfolder."""
        target_dir = self._base_dir / subfolder
        if not target_dir.exists():
            return []

        results = []
        for file in sorted(target_dir.glob("*"), key=os.path.getmtime, reverse=True):
            if file.is_file() and not file.name.startswith("."):
                stat = file.stat()
                results.append({
                    "ref": f"artifact://{subfolder}/{file.name}",
                    "filename": file.name,
                    "size_bytes": stat.st_size,
                    "created_at": stat.st_ctime,
                })
        return results


# Module-level singleton helper
_artifact_manager: ArtifactManager | None = None


def get_artifact_manager() -> ArtifactManager:
    """Return the global artifact manager instance."""
    global _artifact_manager
    if _artifact_manager is None:
        _artifact_manager = ArtifactManager()
    return _artifact_manager
