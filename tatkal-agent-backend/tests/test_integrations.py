"""Tests for the integration registry."""

import pytest

from app.core.exceptions import IntegrationNotRegisteredError, ResourceConflictError
from app.integrations.registry import IntegrationRegistry


class TestIntegrationRegistration:
    """Verify adapter registration and retrieval."""

    def test_register_and_retrieve(self):
        registry = IntegrationRegistry()
        adapter = object()
        registry.register("scheduler", adapter)
        assert registry.get("scheduler") is adapter

    def test_is_registered(self):
        registry = IntegrationRegistry()
        assert registry.is_registered("scheduler") is False
        registry.register("scheduler", object())
        assert registry.is_registered("scheduler") is True

    def test_registered_names(self):
        registry = IntegrationRegistry()
        registry.register("b_module", object())
        registry.register("a_module", object())
        assert registry.registered_names() == ["a_module", "b_module"]


class TestDuplicateRegistration:
    """Verify that duplicate registration is detected."""

    def test_duplicate_raises_conflict(self):
        registry = IntegrationRegistry()
        registry.register("scheduler", object())
        with pytest.raises(ResourceConflictError):
            registry.register("scheduler", object())

    def test_force_overwrite_allowed(self):
        registry = IntegrationRegistry()
        adapter1 = object()
        adapter2 = object()
        registry.register("scheduler", adapter1)
        registry.register("scheduler", adapter2, force=True)
        assert registry.get("scheduler") is adapter2


class TestMissingIntegration:
    """Verify clear errors for unregistered integrations."""

    def test_get_missing_raises_error(self):
        registry = IntegrationRegistry()
        with pytest.raises(IntegrationNotRegisteredError) as exc_info:
            registry.get("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_get_optional_returns_none(self):
        registry = IntegrationRegistry()
        assert registry.get_optional("nonexistent") is None


class TestRegistryCleanup:
    """Verify registry clear for test isolation."""

    def test_clear_removes_all(self):
        registry = IntegrationRegistry()
        registry.register("a", object())
        registry.register("b", object())
        registry.clear()
        assert registry.registered_names() == []
        assert registry.is_registered("a") is False
