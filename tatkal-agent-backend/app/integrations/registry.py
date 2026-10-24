"""
Integration adapter registry.

Provides a simple dependency-injection mechanism for registering and
retrieving integration adapters by interface name.

Features:
    - Register an adapter under a stable interface name.
    - Retrieve a registered adapter.
    - Detect duplicate registrations.
    - Produce a clear error if a required adapter is missing.
    - Support test doubles / mock implementations.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.exceptions import IntegrationNotRegisteredError, ResourceConflictError

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Thread-safe registry for integration adapters.

    Usage::

        registry = IntegrationRegistry()
        registry.register("scheduler", my_scheduler_adapter)
        scheduler = registry.get("scheduler")
    """

    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}

    def register(self, name: str, adapter: Any, *, force: bool = False) -> None:
        """
        Register an adapter under *name*.

        Args:
            name: Stable interface identifier (e.g. ``"scheduler"``).
            adapter: The adapter instance implementing the corresponding protocol.
            force: If ``True``, overwrite an existing registration (useful in tests).

        Raises:
            ResourceConflictError: If *name* is already registered and *force* is False.
        """
        if name in self._adapters and not force:
            raise ResourceConflictError(
                f"Integration '{name}' is already registered. "
                "Use force=True to replace it (e.g. in tests)."
            )
        self._adapters[name] = adapter
        logger.info("Integration registered: %s", name)

    def get(self, name: str) -> Any:
        """
        Retrieve the adapter registered under *name*.

        Raises:
            IntegrationNotRegisteredError: If no adapter has been registered.
        """
        if name not in self._adapters:
            raise IntegrationNotRegisteredError(name)
        return self._adapters[name]

    def get_optional(self, name: str) -> Any | None:
        """Return the adapter if registered, otherwise ``None``."""
        return self._adapters.get(name)

    def is_registered(self, name: str) -> bool:
        """Check whether an adapter is registered under *name*."""
        return name in self._adapters

    def registered_names(self) -> list[str]:
        """Return a sorted list of all registered adapter names."""
        return sorted(self._adapters.keys())

    def clear(self) -> None:
        """Remove all registrations (primarily for testing)."""
        self._adapters.clear()
        logger.info("Integration registry cleared")

    # ── Tool Adapter Extensions (Phase 4) ─────────────────────────────

    def register_tool(self, name: str, tool: Any, *, force: bool = False) -> None:
        """
        Register a tool adapter under *name*.

        Tools can be looked up using either the bare name (e.g. ``"browser"``)
        or prefixed (``"tool:browser"``).

        Raises:
            ResourceConflictError: If already registered and force=False.
        """
        # Ensure consistent naming
        canonical_name = name.removeprefix("tool:")
        if canonical_name in self._adapters and not force:
            raise ResourceConflictError(
                f"Tool '{canonical_name}' is already registered. "
                "Use force=True to replace it (e.g. in tests)."
            )
        self._adapters[canonical_name] = tool
        logger.info("Tool adapter registered: %s", canonical_name)

    def get_tool(self, name: str) -> Any:
        """
        Retrieve a tool adapter by name or prefixed name.

        Raises:
            IntegrationNotRegisteredError: If the tool is not registered.
        """
        canonical_name = name.removeprefix("tool:")
        if canonical_name in self._adapters:
            return self._adapters[canonical_name]
        if name in self._adapters:
            return self._adapters[name]
        raise IntegrationNotRegisteredError(canonical_name)

    def is_tool_registered(self, name: str) -> bool:
        """Check whether a tool adapter is registered."""
        canonical_name = name.removeprefix("tool:")
        return canonical_name in self._adapters or name in self._adapters

    def list_tools(self) -> list[Any]:
        """
        Return metadata for all registered tool adapters.

        Only includes adapters that provide a ``get_metadata`` method or
        are identified as tool adapters.
        """
        from app.integrations.contracts import ToolMetadata
        results: list[ToolMetadata] = []
        for name, adapter in sorted(self._adapters.items()):
            if hasattr(adapter, "get_metadata") and callable(adapter.get_metadata):
                try:
                    meta = adapter.get_metadata()
                    if isinstance(meta, ToolMetadata):
                        results.append(meta)
                    elif isinstance(meta, dict):
                        results.append(ToolMetadata.model_validate(meta))
                except Exception as exc:
                    logger.warning("Error getting metadata for tool '%s': %s", name, exc)
                    results.append(
                        ToolMetadata(
                            name=name,
                            description=getattr(adapter, "__doc__", "") or "",
                            is_available=False,
                            health_status={"error": str(exc)},
                        )
                    )
            elif hasattr(adapter, "execute") and hasattr(adapter, "health_check"):
                results.append(
                    ToolMetadata(
                        name=name,
                        description=getattr(adapter, "__doc__", "") or f"Tool adapter for {name}",
                        capabilities=[name],
                        is_available=True,
                    )
                )
        return results

    async def check_tool_health(self, name: str) -> dict[str, Any]:
        """Check the health of a specific tool adapter."""
        tool = self.get_tool(name)
        canonical_name = name.removeprefix("tool:")
        if hasattr(tool, "health_check") and callable(tool.health_check):
            try:
                import inspect
                if inspect.iscoroutinefunction(tool.health_check):
                    is_healthy = await tool.health_check()
                else:
                    is_healthy = tool.health_check()
                return {
                    "tool": canonical_name,
                    "healthy": bool(is_healthy),
                    "status": "healthy" if is_healthy else "degraded",
                }
            except Exception as exc:
                logger.warning("Health check failed for tool '%s': %s", canonical_name, exc)
                return {
                    "tool": canonical_name,
                    "healthy": False,
                    "status": "unhealthy",
                    "error": str(exc),
                }
        return {
            "tool": canonical_name,
            "healthy": True,
            "status": "unknown (no health_check method)",
        }

    async def check_all_tools_health(self) -> dict[str, dict[str, Any]]:
        """Run health checks on all registered tool adapters."""
        results: dict[str, dict[str, Any]] = {}
        for meta in self.list_tools():
            results[meta.name] = await self.check_tool_health(meta.name)
        return results

    # ── Teammate Module Integration Extensions (Phase 5) ──────────────

    def list_integrations(self) -> list[dict[str, Any]]:
        """
        Return metadata or descriptor dicts for all registered teammate integrations.
        """
        results: list[dict[str, Any]] = []
        for name, adapter in sorted(self._adapters.items()):
            meta: dict[str, Any] = {
                "name": name,
                "is_registered": True,
            }
            if hasattr(adapter, "get_metadata") and callable(adapter.get_metadata):
                try:
                    m = adapter.get_metadata()
                    if hasattr(m, "model_dump"):
                        meta.update(m.model_dump())
                    elif isinstance(m, dict):
                        meta.update(m)
                except Exception as exc:
                    logger.warning("Error getting metadata for integration '%s': %s", name, exc)
                    meta["error"] = str(exc)
            else:
                meta["description"] = getattr(adapter, "__doc__", "") or f"Integration {name}"
            results.append(meta)
        return results

    async def check_integration_health(self, name: str) -> dict[str, Any]:
        """Check the health of a specific registered integration."""
        adapter = self.get(name)
        if hasattr(adapter, "health_check") and callable(adapter.health_check):
            try:
                import inspect
                if inspect.iscoroutinefunction(adapter.health_check):
                    is_healthy = await adapter.health_check()
                else:
                    is_healthy = adapter.health_check()
                return {
                    "integration": name,
                    "healthy": bool(is_healthy),
                    "status": "healthy" if is_healthy else "degraded",
                }
            except Exception as exc:
                logger.warning("Health check failed for integration '%s': %s", name, exc)
                return {
                    "integration": name,
                    "healthy": False,
                    "status": "unhealthy",
                    "error": str(exc),
                }
        return {
            "integration": name,
            "healthy": True,
            "status": "operational (no health_check method)",
        }

    async def check_all_integrations_health(self) -> dict[str, dict[str, Any]]:
        """Run health checks on all registered adapters."""
        results: dict[str, dict[str, Any]] = {}
        for name in self.registered_names():
            results[name] = await self.check_integration_health(name)
        return results



# ── Module-level singleton ───────────────────────────────────────
_registry: IntegrationRegistry | None = None


def get_registry() -> IntegrationRegistry:
    """Return the application-wide integration registry."""
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (for testing)."""
    global _registry
    _registry = None
