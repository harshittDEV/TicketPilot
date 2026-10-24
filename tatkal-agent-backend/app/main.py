"""
Tatkal Agent Backend — FastAPI application entry point.

Responsibilities:
    - Create and configure the FastAPI application.
    - Register routers, middleware, and exception handlers.
    - Initialise the database on startup.
    - Keep this file small — no business logic here.

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.database.init_db import init_db

logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler (replaces deprecated on_event)."""
    settings = get_settings()
    setup_logging(settings.log_level)
    settings.ensure_directories()

    logger.info(
        "Starting %s [env=%s, api=%s]",
        settings.app_name,
        settings.app_env,
        settings.api_version,
    )

    # Initialise database tables (safe to call repeatedly)
    try:
        init_db()
        logger.info("Database initialised successfully")
    except Exception:
        logger.exception("Database initialisation failed — app will start in degraded mode")

    # Initialise default tool adapters and skills (safe to call repeatedly)
    try:
        from app.integrations.registry import get_registry
        from app.tools.browser.adapter import BrowserToolAdapter
        from app.tools.desktop.adapter import DesktopToolAdapter
        from app.skills.loader import get_skill_loader

        registry = get_registry()
        if not registry.is_registered("browser") and not registry.is_tool_registered("browser"):
            registry.register_tool("browser", BrowserToolAdapter())
        if not registry.is_registered("desktop") and not registry.is_tool_registered("desktop"):
            registry.register_tool("desktop", DesktopToolAdapter())

        get_skill_loader().load_all()
        logger.info("Default tool adapters and skills registered successfully")

        # Initialise teammate integration adapters (Phase 5)
        from app.integrations.scheduler.adapter import TatkalSchedulerAdapter
        from app.integrations.train_comparison.adapter import TrainComparisonAdapter
        from app.integrations.security.adapter import SecurityAdapter
        from app.integrations.booking.adapter import BookingAssistanceAdapter

        if not registry.is_registered("scheduler"):
            registry.register("scheduler", TatkalSchedulerAdapter())
        if not registry.is_registered("train_comparison"):
            registry.register("train_comparison", TrainComparisonAdapter())
        if not registry.is_registered("security"):
            registry.register("security", SecurityAdapter())
        if not registry.is_registered("booking_assistance"):
            registry.register("booking_assistance", BookingAssistanceAdapter())

        logger.info("Default teammate integrations registered successfully")
    except Exception:
        logger.exception("Failed to register tool adapters, skills, or teammate integrations")

    # Start background scheduled execution engine
    scheduler_engine = None
    try:
        from app.services.scheduler_engine import get_scheduler_engine
        scheduler_engine = get_scheduler_engine()
        await scheduler_engine.start()
        logger.info("Agent scheduler background engine started successfully")
    except Exception:
        logger.exception("Failed to start agent scheduler background engine")

    yield  # ← application runs here

    logger.info("Shutting down %s", settings.app_name)
    if scheduler_engine:
        try:
            await scheduler_engine.stop()
            logger.info("Agent scheduler background engine stopped cleanly")
        except Exception as exc:
            logger.warning("Error stopping scheduler engine: %s", exc)

    try:
        import inspect
        from app.integrations.registry import get_registry
        registry = get_registry()
        for tool_meta in registry.list_tools():
            adapter = registry.get_tool(tool_meta.name)
            if hasattr(adapter, "close") and callable(adapter.close):
                if inspect.iscoroutinefunction(adapter.close):
                    await adapter.close()
                else:
                    adapter.close()
        logger.info("Tool adapters cleaned up successfully")
    except Exception as exc:
        logger.warning("Error during tool cleanup on shutdown: %s", exc)


# ── Application factory ─────────────────────────────────────────

def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        description=(
            "Core backend for the Tatkal Booking Agent — a general-purpose "
            "computer-use AI agent. Provides task infrastructure, integration "
            "contracts, and orchestration interfaces."
        ),
        version=settings.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow configured frontend origins during development
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(application)

    # API routers
    from app.api.health import router as root_health_router
    application.include_router(root_health_router)
    application.include_router(api_v1_router)

    return application


# ── Module-level instance (used by uvicorn) ──────────────────────
app = create_app()
