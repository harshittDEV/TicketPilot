"""
Database initialization.

Creates all tables defined via the declarative Base.
In later phases, this may be replaced or supplemented by Alembic migrations.
"""

from __future__ import annotations

import logging

from app.database.base import Base
from app.database.session import get_engine
import app.models  # noqa: F401 — ensure all ORM models are registered with Base

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Create all tables that do not yet exist.

    This is safe to call multiple times — existing tables are not dropped.

    Future phases:
        When the schema stabilises, introduce Alembic for versioned
        migrations. At that point, ``init_db()`` can delegate to
        ``alembic upgrade head`` or remain as a fallback for fresh
        development databases.
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialised (create_all)")
