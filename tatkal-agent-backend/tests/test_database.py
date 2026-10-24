"""Tests for database foundation."""

import os
import tempfile

import pytest
from sqlalchemy import text

from app.database.base import Base
from app.database.session import (
    check_database_connection,
    get_db,
    get_engine,
    get_session_factory,
    reset_engine,
)


class TestDatabaseConnectivity:
    """Verify engine creation and connectivity checks."""

    def test_engine_creation_with_temp_db(self, tmp_db_url: str):
        engine = get_engine(tmp_db_url)
        assert engine is not None

    def test_connectivity_check_succeeds(self, tmp_db_url: str):
        get_engine(tmp_db_url)
        assert check_database_connection() is True

    def test_connectivity_check_fails_gracefully(self):
        """When the database engine cannot connect, check returns False."""
        from unittest.mock import patch, MagicMock

        reset_engine()
        # Create a mock engine whose connect() raises an exception
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("connection refused")

        with patch("app.database.session.get_engine", return_value=mock_engine):
            result = check_database_connection()
        assert result is False


class TestSessionLifecycle:
    """Verify session factory and FastAPI dependency."""

    def test_session_factory_returns_session(self, tmp_db_url: str):
        engine = get_engine(tmp_db_url)
        factory = get_session_factory(engine)
        session = factory()
        try:
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        finally:
            session.close()

    def test_get_db_dependency_yields_and_closes(self, tmp_db_url: str):
        get_engine(tmp_db_url)
        gen = get_db()
        session = next(gen)
        assert session is not None
        # Simulate request completion
        try:
            next(gen)
        except StopIteration:
            pass  # Expected — generator exhausted

    def test_create_all_tables(self, tmp_db_url: str):
        """Base.metadata.create_all should work without errors on a fresh DB."""
        engine = get_engine(tmp_db_url)
        Base.metadata.create_all(bind=engine)
        # No exception means success — no tables defined yet in Phase 1


class TestEngineReset:
    """Verify engine reset for test isolation."""

    def test_reset_allows_new_engine(self, tmp_db_url: str):
        engine1 = get_engine(tmp_db_url)
        reset_engine()
        # Create a second temporary DB
        fd, path2 = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        url2 = f"sqlite:///{path2}"
        try:
            engine2 = get_engine(url2)
            assert engine1 is not engine2
        finally:
            os.unlink(path2)
