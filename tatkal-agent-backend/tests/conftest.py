"""
Shared test fixtures.

Provides:
    - Isolated temporary database for each test session.
    - FastAPI test client.
    - Clean settings and registry per test.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import reset_settings
from app.database.session import reset_engine
from app.integrations.registry import reset_registry
from app.services.audit_service import reset_audit_service
from app.services.evidence_service import reset_evidence_service


@pytest.fixture(autouse=True)
def _isolate_globals():
    """Reset global singletons before and after every test."""
    reset_settings()
    reset_engine()
    reset_registry()
    reset_audit_service()
    reset_evidence_service()
    yield
    reset_settings()
    reset_engine()
    reset_registry()
    reset_audit_service()
    reset_evidence_service()


@pytest.fixture()
def tmp_db_path() -> Generator[str, None, None]:
    """Create a temporary SQLite database file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture()
def tmp_db_url(tmp_db_path: str) -> str:
    """Return a SQLite URL pointing to a temporary database file."""
    return f"sqlite:///{tmp_db_path}"


@pytest.fixture()
def client(tmp_db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """
    Return a TestClient backed by a temporary database.

    Uses monkeypatch to inject the temp DB URL before importing the app.
    """
    monkeypatch.setenv("DATABASE_URL", tmp_db_url)

    # Force fresh singletons with the patched env
    reset_settings()
    reset_engine()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as tc:
        yield tc
