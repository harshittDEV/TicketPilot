"""
Centralized application configuration using pydantic-settings.

All configuration is driven by environment variables with sensible development defaults.
Real secrets must never be committed — use .env files locally.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root: two levels up from this file (app/core/config.py → app/ → tatkal-agent-backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings populated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "Tatkal Agent Backend"
    app_env: str = "development"  # development | staging | production
    api_version: str = "v1"
    debug: bool = True

    # ── Server ───────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8000

    # ── Database ─────────────────────────────────────────────────
    database_url: str = f"sqlite:///{_PROJECT_ROOT / 'data' / 'tatkal_agent.db'}"

    # ── Logging ──────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Storage ──────────────────────────────────────────────────
    artifact_dir: str = str(_PROJECT_ROOT / "artifacts")
    data_dir: str = str(_PROJECT_ROOT / "data")

    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # ── Model Provider Placeholders ──────────────────────────────
    # These are *optional* — the app must start without them.
    model_provider: Optional[str] = None        # e.g. "openai", "anthropic", "gemini"
    model_api_key: Optional[str] = None         # secret — never log or expose
    model_name: Optional[str] = None            # e.g. "gpt-4o", "claude-sonnet-4-20250514"
    model_base_url: Optional[str] = None        # custom endpoint override

    # ── Tool Adapters & Skills (Phase 4) ─────────────────────────
    enable_browser_adapter: bool = True
    browser_headless: bool = True
    browser_navigation_timeout: float = 30.0
    browser_action_timeout: float = 15.0

    enable_desktop_adapter: bool = False        # Disabled by default for safety / headless
    desktop_action_timeout: float = 10.0

    skills_dir: str = str(_PROJECT_ROOT / "app" / "skills" / "definitions")
    max_artifact_size_bytes: int = 5 * 1024 * 1024   # 5 MB
    max_observation_text_chars: int = 5000           # Bound visible text excerpt length

    # ── Recovery & Resilience (Phase 6) ──────────────────────────
    recovery_max_attempts: int = 3
    recovery_initial_backoff: float = 0.5
    recovery_backoff_multiplier: float = 2.0
    recovery_max_backoff: float = 5.0
    recovery_max_cumulative_time: float = 30.0

    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_seconds: float = 30.0
    circuit_breaker_half_open_probes: int = 1
    circuit_breaker_window_seconds: float = 60.0

    # ── Audit, Evidence & Compliance (Phase 7) ───────────────────
    audit_enabled: bool = True
    evidence_retention_days: int = 30
    evidence_capture_screenshots: bool = True
    evidence_allowed_types: list[str] = [
        "SCREENSHOT",
        "DOM_SNAPSHOT",
        "TOOL_RESULT_SNAPSHOT",
        "EXECUTION_SUMMARY",
        "ERROR_SNAPSHOT",
    ]

    # ── Railway Data Providers (Phase 9) ─────────────────────────
    railway_provider: str = "hybrid"            # hybrid | static | rapidapi
    railway_api_key: Optional[str] = None       # API key for RapidAPI / external provider (never logged)
    railway_api_host: str = "indian-railway-irctc.p.rapidapi.com"
    railway_api_base_url: str = "https://indian-railway-irctc.p.rapidapi.com"
    railway_timeout_seconds: float = 5.0
    railway_cache_ttl_stations_seconds: int = 86400 * 7   # 7 days for station directory
    railway_cache_ttl_timetable_seconds: int = 86400       # 24 hours for train timetables
    railway_cache_ttl_live_seconds: int = 120              # 2 minutes for live status
    railway_cache_ttl_availability_seconds: int = 300      # 5 minutes for seat availability

    # ── Validators ───────────────────────────────────────────────
    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}, got '{v}'")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v = v.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{v}'")
        return v

    # ── Helpers ──────────────────────────────────────────────────
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def ensure_directories(self) -> None:
        """Create data and artifact directories if they do not exist."""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.artifact_dir, exist_ok=True)


# ── Singleton accessor ───────────────────────────────────────────
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached application settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset cached settings (useful for testing)."""
    global _settings
    _settings = None
