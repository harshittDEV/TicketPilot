"""
Desktop tool adapter conforming to AgentToolIntegration.

Executes desktop interactions (screenshot, click, type, keypress) with
strict OS permission guards and safe error normalization.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import get_settings
from app.integrations.contracts import ToolAction, ToolActionStatus, ToolExecutionResult
from app.tools.artifacts import ArtifactManager, get_artifact_manager
from app.tools.base import BaseToolAdapter
from app.tools.desktop.driver import (
    DesktopDriver,
    DesktopDriverError,
    DesktopPermissionDeniedError,
    DesktopUnsupportedEnvironmentError,
    MockDesktopDriver,
)

logger = logging.getLogger(__name__)

DESKTOP_CAPABILITIES = [
    "screenshot",
    "session_status",
    "click",
    "type_text",
    "press_key",
    "health",
]


class DesktopToolAdapter(BaseToolAdapter):
    """
    Adapter providing desktop automation.

    Isolated from browser automation. Requires explicit enablement via
    ``ENABLE_DESKTOP_ADAPTER=true`` or manual injection of an authorized driver.
    """

    def __init__(
        self,
        driver: Optional[DesktopDriver] = None,
        artifact_manager: Optional[ArtifactManager] = None,
        *,
        is_available: Optional[bool] = None,
    ) -> None:
        settings = get_settings()
        availability = is_available if is_available is not None else settings.enable_desktop_adapter
        super().__init__(
            name="desktop",
            description="Desktop automation tool for display capture and mouse/keyboard interaction",
            version="1.0.0",
            capabilities=DESKTOP_CAPABILITIES,
            input_schema={
                "screenshot": {"type": "object"},
                "session_status": {"type": "object"},
                "click": {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                    "required": ["x", "y"],
                },
                "type_text": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                "press_key": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                },
                "health": {"type": "object"},
            },
            is_available=availability,
        )
        self._driver = driver or MockDesktopDriver()
        self._artifact_manager = artifact_manager or get_artifact_manager()

    @property
    def driver(self) -> DesktopDriver:
        return self._driver

    def set_driver(self, driver: DesktopDriver) -> None:
        """Inject an alternative desktop driver."""
        self._driver = driver

    def validate_action(self, action: ToolAction) -> None:
        super().validate_action(action)
        act = action.action_type
        params = action.parameters

        if act == "click":
            if "x" not in params or "y" not in params:
                raise ValueError("Parameters 'x' and 'y' are required for action 'click'")
            if not isinstance(params["x"], int) or not isinstance(params["y"], int):
                raise ValueError("Coordinates 'x' and 'y' must be integers")
            if params["x"] < 0 or params["y"] < 0:
                raise ValueError("Coordinates cannot be negative")

        elif act == "type_text":
            if "text" not in params:
                raise ValueError("Parameter 'text' is required for action 'type_text'")

        elif act == "press_key":
            if not params.get("key"):
                raise ValueError("Parameter 'key' is required for action 'press_key'")

    async def _dispatch(self, action: ToolAction) -> ToolExecutionResult:
        act = action.action_type
        params = action.parameters

        try:
            if act == "session_status":
                status_info = await self._driver.check_availability()
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=status_info)

            elif act == "screenshot":
                run_id = params.get("run_id")
                image_bytes = await self._driver.capture_screenshot()
                artifact_ref = self._artifact_manager.save_screenshot(
                    image_bytes, format="png", prefix="desktop", run_id=run_id
                )
                return ToolExecutionResult(
                    status=ToolActionStatus.SUCCESS,
                    output={"artifact_ref": artifact_ref, "size_bytes": len(image_bytes)},
                    metadata={"artifact_ref": artifact_ref},
                )

            elif act == "click":
                output = await self._driver.click(int(params["x"]), int(params["y"]))
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "type_text":
                output = await self._driver.type_text(str(params["text"]))
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "press_key":
                output = await self._driver.press_key(str(params["key"]))
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "health":
                avail = await self._driver.check_availability()
                return ToolExecutionResult(
                    status=ToolActionStatus.SUCCESS,
                    output={"healthy": self._is_available, "availability": avail},
                )

            else:
                return ToolExecutionResult(
                    status=ToolActionStatus.INVALID_ARGUMENTS,
                    error_message=f"Unsupported desktop action '{act}'",
                )

        except DesktopPermissionDeniedError as exc:
            logger.warning("Desktop permission required: %s", exc)
            return ToolExecutionResult(
                status=ToolActionStatus.HUMAN_INTERVENTION_REQUIRED,
                error_message=str(exc),
                output={"intervention_reason": "permission_denied", "message": str(exc)},
            )
        except DesktopUnsupportedEnvironmentError as exc:
            return ToolExecutionResult(
                status=ToolActionStatus.TOOL_UNAVAILABLE,
                error_message=str(exc),
            )
        except Exception as exc:
            logger.exception("Unexpected desktop action error: %s", exc)
            return ToolExecutionResult(
                status=ToolActionStatus.NON_RECOVERABLE_FAILURE,
                error_message=f"Desktop error: {exc!s}",
            )

    async def health_check(self) -> bool:
        if not self._is_available:
            return False
        try:
            return await self._driver.is_supported()
        except Exception:
            return False
