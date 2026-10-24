"""
Browser tool adapter conforming to AgentToolIntegration.

Executes structured browser operations, handles challenge detection,
normalizes errors, and records screenshot artifacts safely.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.config import get_settings
from app.integrations.contracts import ToolAction, ToolActionStatus, ToolExecutionResult
from app.tools.artifacts import ArtifactManager, get_artifact_manager
from app.tools.base import BaseToolAdapter
from app.tools.browser.driver import (
    BrowserChallengeDetected,
    BrowserDriver,
    BrowserDriverError,
    MockBrowserDriver,
)

logger = logging.getLogger(__name__)

BROWSER_CAPABILITIES = [
    "navigate",
    "inspect",
    "extract_text",
    "click",
    "type_text",
    "get_url_and_title",
    "screenshot",
    "health",
]


class BrowserToolAdapter(BaseToolAdapter):
    """
    Adapter providing safe browser automation.

    Decoupled from underlying browser libraries (Playwright or mock) via
    ``BrowserDriver``.
    """

    def __init__(
        self,
        driver: Optional[BrowserDriver] = None,
        artifact_manager: Optional[ArtifactManager] = None,
        *,
        is_available: bool = True,
    ) -> None:
        settings = get_settings()
        super().__init__(
            name="browser",
            description="Automated browser tool for web navigation, inspection, and interaction",
            version="1.0.0",
            capabilities=BROWSER_CAPABILITIES,
            input_schema={
                "navigate": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
                "click": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
                "type_text": {
                    "type": "object",
                    "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
                    "required": ["selector", "text"],
                },
                "extract_text": {"type": "object", "properties": {"selector": {"type": "string"}, "max_chars": {"type": "integer"}}},
                "inspect": {"type": "object"},
                "get_url_and_title": {"type": "object"},
                "screenshot": {"type": "object"},
                "health": {"type": "object"},
            },
            is_available=is_available and settings.enable_browser_adapter,
        )
        self._driver = driver or MockBrowserDriver()
        self._artifact_manager = artifact_manager or get_artifact_manager()
        self._nav_timeout = settings.browser_navigation_timeout
        self._action_timeout = settings.browser_action_timeout

    @property
    def driver(self) -> BrowserDriver:
        return self._driver

    def set_driver(self, driver: BrowserDriver) -> None:
        """Inject an alternative browser driver."""
        self._driver = driver

    def validate_action(self, action: ToolAction) -> None:
        super().validate_action(action)
        act = action.action_type
        params = action.parameters

        if act == "navigate":
            url = params.get("url")
            if not url or not isinstance(url, str):
                raise ValueError("Parameter 'url' is required for action 'navigate'")
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL scheme '{parsed.scheme}'. Only http and https are permitted.")

        elif act == "click":
            if not params.get("selector"):
                raise ValueError("Parameter 'selector' is required for action 'click'")

        elif act == "type_text":
            if not params.get("selector"):
                raise ValueError("Parameter 'selector' is required for action 'type_text'")
            if "text" not in params:
                raise ValueError("Parameter 'text' is required for action 'type_text'")

    async def _dispatch(self, action: ToolAction) -> ToolExecutionResult:
        act = action.action_type
        params = action.parameters
        timeout = action.timeout_seconds or self._action_timeout

        try:
            if act == "navigate":
                url = params["url"]
                nav_timeout = params.get("timeout_seconds", self._nav_timeout)
                output = await self._driver.navigate(url, timeout=nav_timeout)
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "inspect":
                output = await self._driver.inspect_page()
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "get_url_and_title":
                output = await self._driver.get_url_and_title()
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "extract_text":
                selector = params.get("selector")
                max_chars = int(params.get("max_chars", 5000))
                text = await self._driver.extract_text(selector=selector, max_chars=max_chars)
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output={"text": text, "length": len(text)})

            elif act == "click":
                selector = params["selector"]
                output = await self._driver.click(selector, timeout=timeout)
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "type_text":
                selector = params["selector"]
                text = str(params["text"])
                clear_first = bool(params.get("clear_first", True))
                output = await self._driver.type_text(selector, text, clear_first=clear_first, timeout=timeout)
                return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output=output)

            elif act == "screenshot":
                run_id = params.get("run_id")
                image_bytes = await self._driver.capture_screenshot()
                artifact_ref = self._artifact_manager.save_screenshot(
                    image_bytes, format="png", prefix="browser", run_id=run_id
                )
                return ToolExecutionResult(
                    status=ToolActionStatus.SUCCESS,
                    output={"artifact_ref": artifact_ref, "size_bytes": len(image_bytes)},
                    metadata={"artifact_ref": artifact_ref},
                )

            elif act == "health":
                is_running = await self._driver.is_running()
                return ToolExecutionResult(
                    status=ToolActionStatus.SUCCESS,
                    output={"healthy": True, "session_running": is_running, "adapter": "browser"},
                )

            else:
                return ToolExecutionResult(
                    status=ToolActionStatus.INVALID_ARGUMENTS,
                    error_message=f"Unsupported action '{act}'",
                )

        except BrowserChallengeDetected as exc:
            logger.warning("Human intervention required: %s", exc)
            return ToolExecutionResult(
                status=ToolActionStatus.HUMAN_INTERVENTION_REQUIRED,
                error_message=str(exc),
                output={"intervention_reason": "challenge_detected", "message": str(exc)},
            )
        except TimeoutError as exc:
            return ToolExecutionResult(
                status=ToolActionStatus.TIMEOUT,
                error_message=f"Browser action '{act}' timed out: {exc!s}",
            )
        except BrowserDriverError as exc:
            return ToolExecutionResult(
                status=ToolActionStatus.RECOVERABLE_FAILURE,
                error_message=f"Browser driver error: {exc!s}",
            )
        except Exception as exc:
            logger.exception("Unexpected browser action error: %s", exc)
            return ToolExecutionResult(
                status=ToolActionStatus.NON_RECOVERABLE_FAILURE,
                error_message=f"Unexpected error: {exc!s}",
            )

    async def health_check(self) -> bool:
        if not self._is_available:
            return False
        try:
            return bool(self._driver)
        except Exception:
            return False

    async def close(self) -> None:
        """Clean up browser driver sessions and resources."""
        if self._driver:
            try:
                await self._driver.stop()
                logger.info("Browser driver stopped cleanly")
            except Exception as exc:
                logger.warning("Error stopping browser driver: %s", exc)
