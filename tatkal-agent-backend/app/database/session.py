"""
Database engine and session management.

Provides a reusable engine, session factory, and a FastAPI dependency
that correctly manages session lifecycle (one session per request,
always closed).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Module-level singletons ──────────────────────────────────────
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def _ensure_db_directory(db_url: str) -> None:
    """Create the parent directory for a SQLite database file if needed."""
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "", 1)
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)


def get_engine(database_url: str | None = None) -> Engine:
    """
    Return the singleton database engine.

    Creates the engine on first call. Subsequent calls return the same
    instance unless ``reset_engine()`` has been called.
    """
    global _engine
    if _engine is not None:
        return _engine

    url = database_url or get_settings().database_url
    _ensure_db_directory(url)

    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False,
    )

    # Enable WAL mode for SQLite for better concurrent read/write
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    logger.info("Database engine created for: %s", _sanitize_url(url))
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return the singleton session factory, creating it if necessary."""
    global _SessionLocal
    if _SessionLocal is not None:
        return _SessionLocal

    eng = engine or get_engine()
    _SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.

    The session is always closed after the request completes,
    regardless of success or failure.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


from contextlib import contextmanager


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for standalone non-request database sessions."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()



def check_database_connection() -> bool:
    """
    Attempt a lightweight query to verify database connectivity.

    Returns True if the database is reachable, False otherwise.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database connectivity check failed")
        return False


def reset_engine() -> None:
    """Dispose of the current engine and session factory (for testing)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _SessionLocal = None


def _sanitize_url(url: str) -> str:
    """Remove credentials from a database URL for safe logging."""
    if "@" in url:
        scheme_end = url.index("://") + 3
        at_pos = url.index("@")
        return url[:scheme_end] + "***@" + url[at_pos + 1 :]
    return url
