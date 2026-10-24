"""
Base tool adapter infrastructure.

Provides a common foundation for all agent computer-use tools (browser,
desktop, etc.), ensuring consistent argument validation, error normalization,
health checks, and metadata reporting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import time
from typing import Any, Optional

from app.integrations.contracts import (
    AgentToolIntegration,
    ToolAction,
    ToolActionStatus,
    ToolExecutionResult,
    ToolMetadata,
)

logger = logging.getLogger(__name__)


class BaseToolAdapter(ABC):
    """
    Abstract base class for all computer-use tool adapters.

    Subclasses implement ``_dispatch()`` and declare their capabilities.
    The base class provides:
        - Structured input validation.
        - Execution timing.
        - Error normalization into ``ToolExecutionResult``.
        - Metadata reporting conforming to ``ToolMetadata``.
    """

    def __init__(
        self,
        name: str,
        description: str,
        *,
        version: str = "1.0.0",
        capabilities: Optional[list[str]] = None,
        input_schema: Optional[dict[str, Any]] = None,
        is_available: bool = True,
    ) -> None:
        self._name = name
        self._description = description
        self._version = version
        self._capabilities = capabilities or []
        self._input_schema = input_schema or {}
        self._is_available = is_available

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def version(self) -> str:
        return self._version

    @property
    def capabilities(self) -> list[str]:
        return list(self._capabilities)

    @property
    def is_available(self) -> bool:
        return self._is_available

    def set_availability(self, available: bool) -> None:
        """Dynamically mark the tool as available or unavailable."""
        self._is_available = available

    def get_metadata(self) -> ToolMetadata:
        """Return standardized metadata describing this tool."""
        return ToolMetadata(
            name=self._name,
            description=self._description,
            version=self._version,
            capabilities=self.capabilities,
            input_schema=self._input_schema,
            is_available=self._is_available,
            health_status={"available": self._is_available},
        )

    def validate_action(self, action: ToolAction) -> None:
        """
        Validate that the requested action is supported.

        Raises:
            ValueError: If the action_type is not supported or parameters are malformed.
        """
        if self._capabilities and action.action_type not in self._capabilities:
            allowed = ", ".join(self._capabilities)
            raise ValueError(
                f"Action '{action.action_type}' is not supported by tool '{self._name}'. "
                f"Allowed actions: [{allowed}]"
            )

    async def execute(self, action: ToolAction) -> ToolExecutionResult:
        """
        Execute an action with timing, validation, and error normalization.

        Ensures that unexpected exceptions do not crash the orchestrator,
        returning structured ToolExecutionResult objects instead.
        """
        if not self._is_available:
            return ToolExecutionResult(
                status=ToolActionStatus.TOOL_UNAVAILABLE,
                error_message=f"Tool '{self._name}' is currently unavailable",
                duration_seconds=0.0,
            )

        start_time = time.monotonic()
        try:
            self.validate_action(action)
        except ValueError as exc:
            duration = time.monotonic() - start_time
            return ToolExecutionResult(
                status=ToolActionStatus.INVALID_ARGUMENTS,
                error_message=str(exc),
                duration_seconds=duration,
            )

        try:
            result = await self._dispatch(action)
            if result.duration_seconds is None:
                result.duration_seconds = time.monotonic() - start_time
            return result
        except TimeoutError:
            duration = time.monotonic() - start_time
            return ToolExecutionResult(
                status=ToolActionStatus.TIMEOUT,
                error_message=f"Tool '{self._name}' action '{action.action_type}' timed out",
                duration_seconds=duration,
            )
        except Exception as exc:
            duration = time.monotonic() - start_time
            logger.exception("Error executing '%s' on tool '%s'", action.action_type, self._name)
            return ToolExecutionResult(
                status=ToolActionStatus.NON_RECOVERABLE_FAILURE,
                error_message=f"Execution error in {self._name}: {exc!s}",
                duration_seconds=duration,
            )

    @abstractmethod
    async def _dispatch(self, action: ToolAction) -> ToolExecutionResult:
        """Internal dispatch method implemented by subclasses."""
        ...

    async def health_check(self) -> bool:
        """Return True if the tool adapter is operational."""
        return self._is_available
