"""Tests for configuration management."""

import os

import pytest

from app.core.config import Settings, get_settings, reset_settings


class TestConfigurationDefaults:
    """Validate that sensible defaults are applied."""

    def test_default_app_name(self):
        settings = Settings()
        assert settings.app_name == "Tatkal Agent Backend"

    def test_default_environment(self):
        settings = Settings()
        assert settings.app_env == "development"

    def test_default_api_version(self):
        settings = Settings()
        assert settings.api_version == "v1"

    def test_default_log_level(self):
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_is_development_property(self):
        settings = Settings()
        assert settings.is_development is True
        assert settings.is_production is False

    def test_model_provider_optional(self):
        """App must start without model provider credentials."""
        settings = Settings()
        assert settings.model_provider is None
        assert settings.model_api_key is None


class TestConfigurationValidation:
    """Validate that invalid values are rejected."""

    def test_invalid_app_env_rejected(self):
        with pytest.raises(Exception):
            Settings(app_env="invalid_env")

    def test_invalid_log_level_rejected(self):
        with pytest.raises(Exception):
            Settings(log_level="VERBOSE")

    def test_valid_log_level_uppercased(self):
        settings = Settings(log_level="debug")
        assert settings.log_level == "DEBUG"


class TestConfigurationFromEnv:
    """Validate environment variable overrides."""

    def test_env_overrides_app_name(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("APP_NAME", "Test Agent")
        reset_settings()
        settings = get_settings()
        assert settings.app_name == "Test Agent"

    def test_env_overrides_log_level(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        reset_settings()
        settings = get_settings()
        assert settings.log_level == "DEBUG"


class TestConfigurationDirectories:
    """Validate directory creation helpers."""

    def test_ensure_directories_creates_paths(self, tmp_path):
        settings = Settings(
            data_dir=str(tmp_path / "test_data"),
            artifact_dir=str(tmp_path / "test_artifacts"),
        )
        settings.ensure_directories()
        assert os.path.isdir(settings.data_dir)
        assert os.path.isdir(settings.artifact_dir)
