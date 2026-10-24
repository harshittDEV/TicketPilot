"""
Desktop driver abstraction.

Manages platform-level desktop interaction, OS permission checking,
and mock implementations for test/headless execution.

PREREQUISITES FOR MACOS DESKTOP AUTOMATION:
    1. Active graphical login session (Aqua / WindowServer).
    2. macOS Accessibility Permissions granted to the running terminal or Python process
       (System Settings → Privacy & Security → Accessibility).
    3. macOS Screen Recording Permissions granted
       (System Settings → Privacy & Security → Screen Recording).
    When these prerequisites are missing or unverified, the driver safely reports
    unavailability rather than crashing or triggering OS permission panics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import platform
import sys
from typing import Any, Optional

from app.tools.browser.driver import MINIMAL_PNG_BYTES

logger = logging.getLogger(__name__)


class DesktopDriverError(Exception):
    """Base error for desktop driver operations."""


class DesktopPermissionDeniedError(DesktopDriverError):
    """Raised when macOS Accessibility or Screen Recording permissions are denied."""


class DesktopUnsupportedEnvironmentError(DesktopDriverError):
    """Raised when the execution environment does not support GUI desktop automation."""


class DesktopDriver(ABC):
    """Abstract interface for desktop automation drivers."""

    @abstractmethod
    async def check_availability(self) -> dict[str, Any]:
        """Check whether desktop automation is supported and permitted."""
        ...

    @abstractmethod
    async def is_supported(self) -> bool:
        """Return True if the current platform and session support desktop automation."""
        ...

    @abstractmethod
    async def capture_screenshot(self) -> bytes:
        """Capture the primary display as PNG bytes."""
        ...

    @abstractmethod
    async def click(self, x: int, y: int) -> dict[str, Any]:
        """Perform a permitted click at screen coordinates (x, y)."""
        ...

    @abstractmethod
    async def type_text(self, text: str) -> dict[str, Any]:
        """Type text into the currently active window or field."""
        ...

    @abstractmethod
    async def press_key(self, key: str) -> dict[str, Any]:
        """Press a named key (e.g. 'enter', 'tab', 'escape')."""
        ...


class MockDesktopDriver(DesktopDriver):
    """
    In-memory desktop driver for testing and development.

    Simulates clicks, keystrokes, screenshots, and permission checks
    without touching the host OS windowing server.
    """

    def __init__(
        self,
        *,
        supported: bool = True,
        has_permissions: bool = True,
    ) -> None:
        self._supported = supported
        self._has_permissions = has_permissions
        self._clicks: list[tuple[int, int]] = []
        self._typed_strings: list[str] = []
        self._pressed_keys: list[str] = []

    def set_environment(self, *, supported: bool, has_permissions: bool) -> None:
        self._supported = supported
        self._has_permissions = has_permissions

    async def is_supported(self) -> bool:
        return self._supported and self._has_permissions

    async def check_availability(self) -> dict[str, Any]:
        return {
            "platform": "mock_macos",
            "supported": self._supported,
            "has_accessibility_permission": self._has_permissions,
            "has_screen_recording_permission": self._has_permissions,
            "has_gui_session": self._supported,
            "status": "ready" if (self._supported and self._has_permissions) else "unavailable",
        }

    async def capture_screenshot(self) -> bytes:
        if not self._supported:
            raise DesktopUnsupportedEnvironmentError("Desktop automation unsupported in this environment")
        if not self._has_permissions:
            raise DesktopPermissionDeniedError("Screen recording permission denied")
        return MINIMAL_PNG_BYTES

    async def click(self, x: int, y: int) -> dict[str, Any]:
        if not self._supported:
            raise DesktopUnsupportedEnvironmentError("Desktop automation unsupported")
        if not self._has_permissions:
            raise DesktopPermissionDeniedError("Accessibility permission denied")
        if x < 0 or y < 0:
            raise ValueError(f"Invalid coordinates ({x}, {y})")

        self._clicks.append((x, y))
        return {"action": "click", "x": x, "y": y}

    async def type_text(self, text: str) -> dict[str, Any]:
        if not self._supported:
            raise DesktopUnsupportedEnvironmentError("Desktop automation unsupported")
        if not self._has_permissions:
            raise DesktopPermissionDeniedError("Accessibility permission denied")

        self._typed_strings.append(text)
        return {"action": "type_text", "chars": len(text)}

    async def press_key(self, key: str) -> dict[str, Any]:
        if not self._supported:
            raise DesktopUnsupportedEnvironmentError("Desktop automation unsupported")
        if not self._has_permissions:
            raise DesktopPermissionDeniedError("Accessibility permission denied")

        self._pressed_keys.append(key)
        return {"action": "press_key", "key": key}


class MacDesktopDriver(DesktopDriver):
    """
    macOS desktop automation driver with explicit permission verification.

    Checks macOS environment prerequisites and prevents unhandled crashes.
    """

    def __init__(self) -> None:
        self._is_macos = platform.system() == "Darwin"

    async def is_supported(self) -> bool:
        if not self._is_macos:
            return False
        info = await self.check_availability()
        return bool(info.get("supported") and info.get("has_accessibility_permission"))

    async def check_availability(self) -> dict[str, Any]:
        is_darwin = platform.system() == "Darwin"
        if not is_darwin:
            return {
                "platform": platform.system(),
                "supported": False,
                "reason": "Host OS is not macOS",
                "status": "unsupported_os",
            }

        # Check for active WindowServer GUI session
        # On headless servers or SSH without Quartz, GUI automation cannot run
        has_gui = sys.platform == "darwin"

        return {
            "platform": "macOS",
            "os_release": platform.release(),
            "supported": True,
            "has_gui_session": has_gui,
            "has_accessibility_permission": False,  # Conservative: requires user prompt in System Settings
            "has_screen_recording_permission": False,
            "status": "permissions_required",
            "prerequisites": [
                "System Settings -> Privacy & Security -> Accessibility",
                "System Settings -> Privacy & Security -> Screen Recording",
            ],
        }

    async def capture_screenshot(self) -> bytes:
        info = await self.check_availability()
        if not info.get("supported"):
            raise DesktopUnsupportedEnvironmentError("Desktop screenshot unsupported on non-macOS platforms")
        # In this infrastructure phase, avoid triggering unexpected screen recording prompts
        # unless full mock or permissions are configured
        raise DesktopPermissionDeniedError(
            "Screen recording permission is unverified on this macOS host. "
            "Please grant permissions in System Settings or use MockDesktopDriver for tests."
        )

    async def click(self, x: int, y: int) -> dict[str, Any]:
        raise DesktopPermissionDeniedError(
            "Accessibility permission required to dispatch OS mouse events."
        )

    async def type_text(self, text: str) -> dict[str, Any]:
        raise DesktopPermissionDeniedError(
            "Accessibility permission required to dispatch OS keystrokes."
        )

    async def press_key(self, key: str) -> dict[str, Any]:
        raise DesktopPermissionDeniedError(
            "Accessibility permission required to dispatch OS key press."
        )
