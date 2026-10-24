"""
Browser driver abstraction for browser automation.

Provides:
    - ``BrowserDriver``: Abstract protocol defining browser interactions.
    - ``MockBrowserDriver``: High-fidelity in-memory driver for tests and headless environments.
    - ``PlaywrightBrowserDriver``: Real Playwright integration with lazy startup and safety guards.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Valid 1x1 PNG bytes for testing screenshot capture without browser overhead
MINIMAL_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H"
    b"\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


class BrowserDriverError(Exception):
    """Base error for browser driver operations."""


class BrowserChallengeDetected(BrowserDriverError):
    """Raised when an authentication, CAPTCHA, or bot-block screen is encountered."""


class BrowserDriver(ABC):
    """Abstract interface for browser automation drivers."""

    @abstractmethod
    async def start(self) -> None:
        """Start the browser session."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Close the browser session."""
        ...

    @abstractmethod
    async def is_running(self) -> bool:
        """Return True if the browser session is currently active."""
        ...

    @abstractmethod
    async def navigate(self, url: str, timeout: float = 30.0) -> dict[str, Any]:
        """Navigate to a URL."""
        ...

    @abstractmethod
    async def get_url_and_title(self) -> dict[str, str]:
        """Return the current URL and page title."""
        ...

    @abstractmethod
    async def extract_text(self, selector: Optional[str] = None, max_chars: int = 5000) -> str:
        """Extract visible text from page or element, bounded by max_chars."""
        ...

    @abstractmethod
    async def click(self, selector: str, timeout: float = 15.0) -> dict[str, Any]:
        """Click on the element matching selector."""
        ...

    @abstractmethod
    async def type_text(
        self, selector: str, text: str, clear_first: bool = True, timeout: float = 15.0
    ) -> dict[str, Any]:
        """Enter text into the input matching selector."""
        ...

    @abstractmethod
    async def capture_screenshot(self) -> bytes:
        """Capture screenshot as PNG bytes."""
        ...

    @abstractmethod
    async def inspect_page(self) -> dict[str, Any]:
        """Return structured summary of the current page state."""
        ...


class MockBrowserDriver(BrowserDriver):
    """
    In-memory browser driver for testing and development.

    Does not launch any external processes. Simulates page state, element
    interaction, challenge detection, and mock screenshot generation.
    """

    def __init__(self) -> None:
        self._running = False
        self._current_url = "about:blank"
        self._page_title = "Blank Page"
        self._page_text = "Blank page content"
        self._elements: dict[str, dict[str, Any]] = {}
        self._inputs: dict[str, str] = {}
        self._clicks: list[str] = []
        self._pages: dict[str, dict[str, Any]] = {}
        self._has_captcha = False
        self._has_auth_wall = False
        self._should_timeout = False
        self._should_fail = False
        self._failure_message = "Simulated network failure"

    async def start(self) -> None:
        self._running = True
        logger.debug("MockBrowserDriver started")

    async def stop(self) -> None:
        self._running = False
        logger.debug("MockBrowserDriver stopped")

    async def is_running(self) -> bool:
        return self._running

    def set_page(
        self,
        url: str,
        title: str,
        text: str,
        *,
        elements: Optional[dict[str, dict[str, Any]]] = None,
        has_captcha: bool = False,
        has_auth_wall: bool = False,
    ) -> None:
        """Configure mock page content."""
        page_data = {
            "title": title,
            "text": text,
            "elements": elements or {},
            "has_captcha": has_captcha,
            "has_auth_wall": has_auth_wall,
        }
        self._pages[url] = page_data
        self._current_url = url
        self._page_title = title
        self._page_text = text
        self._elements = elements or {}
        self._has_captcha = has_captcha
        self._has_auth_wall = has_auth_wall

    def set_faults(
        self,
        *,
        timeout: bool = False,
        fail: bool = False,
        message: str = "Simulated failure",
    ) -> None:
        """Configure fault injection."""
        self._should_timeout = timeout
        self._should_fail = fail
        self._failure_message = message

    async def navigate(self, url: str, timeout: float = 30.0) -> dict[str, Any]:
        if not self._running:
            await self.start()

        if self._should_timeout:
            raise TimeoutError("Navigation timed out")
        if self._should_fail:
            raise BrowserDriverError(self._failure_message)

        # Check pre-configured page
        if url in self._pages:
            p = self._pages[url]
            self._current_url = url
            self._page_title = p["title"]
            self._page_text = p["text"]
            self._elements = p["elements"]
            self._has_captcha = p["has_captcha"]
            self._has_auth_wall = p["has_auth_wall"]
        # Check for challenge simulation via URL
        elif "captcha" in url.lower() or "challenge" in url.lower():
            self._current_url = url
            self._has_captcha = True
            self._page_title = "Security Challenge"
            self._page_text = "Please complete the CAPTCHA to continue"
        elif "login" in url.lower() or "signin" in url.lower():
            self._current_url = url
            self._has_auth_wall = True
            self._page_title = "Sign In Required"
            self._page_text = "Please enter your username and password"
        else:
            self._current_url = url
            self._page_title = f"Page: {url}"
            self._page_text = f"Rendered content for {url}"

        # Detect challenge triggers
        if self._has_captcha:
            raise BrowserChallengeDetected("CAPTCHA verification screen detected")
        if self._has_auth_wall:
            raise BrowserChallengeDetected("Authentication challenge detected")

        return {
            "url": self._current_url,
            "title": self._page_title,
            "status_code": 200,
        }

    async def get_url_and_title(self) -> dict[str, str]:
        return {
            "url": self._current_url,
            "title": self._page_title,
        }

    async def extract_text(self, selector: Optional[str] = None, max_chars: int = 5000) -> str:
        if selector and selector in self._elements:
            raw_text = self._elements[selector].get("text", "")
        else:
            raw_text = self._page_text
        return raw_text[:max_chars]

    async def click(self, selector: str, timeout: float = 15.0) -> dict[str, Any]:
        if not self._running:
            await self.start()
        if self._should_timeout:
            raise TimeoutError(f"Click on '{selector}' timed out")

        self._clicks.append(selector)
        if selector in self._elements and self._elements[selector].get("triggers_challenge"):
            raise BrowserChallengeDetected("Action triggered security barrier")

        return {"clicked": selector, "timestamp": asyncio.get_event_loop().time()}

    async def type_text(
        self, selector: str, text: str, clear_first: bool = True, timeout: float = 15.0
    ) -> dict[str, Any]:
        if not self._running:
            await self.start()
        if self._should_timeout:
            raise TimeoutError(f"Type into '{selector}' timed out")

        # Sanitize sensitive field detection
        is_sensitive = any(term in selector.lower() for term in ["pass", "pwd", "cvv", "otp", "secret"])
        logged_text = "[REDACTED]" if is_sensitive else text

        self._inputs[selector] = text
        return {
            "selector": selector,
            "entered_chars": len(text),
            "display_value": logged_text,
        }

    async def capture_screenshot(self) -> bytes:
        if not self._running:
            await self.start()
        return MINIMAL_PNG_BYTES

    async def inspect_page(self) -> dict[str, Any]:
        return {
            "url": self._current_url,
            "title": self._page_title,
            "text_excerpt": self._page_text[:500],
            "elements_count": len(self._elements),
            "has_captcha": self._has_captcha,
            "has_auth_wall": self._has_auth_wall,
        }


class PlaywrightBrowserDriver(BrowserDriver):
    """
    Playwright-based browser driver with safety checks.

    Lazy-initializes Playwright. Never runs upon module import.
    """

    def __init__(self, headless: bool = True, default_timeout: float = 30.0) -> None:
        self._headless = headless
        self._default_timeout = default_timeout
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_playwright(self):
        try:
            from playwright.async_api import async_playwright
            return async_playwright
        except ImportError as exc:
            raise BrowserDriverError(
                "Playwright is not installed. Install via 'pip install playwright' "
                "or use MockBrowserDriver for headless/test environments."
            ) from exc

    async def start(self) -> None:
        if self._browser is not None:
            return
        async_playwright = await self._ensure_playwright()
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self._default_timeout * 1000)
        logger.info("Playwright browser session started (headless=%s)", self._headless)

    async def stop(self) -> None:
        if self._page:
            await self._page.close()
            self._page = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Playwright browser session closed")

    async def is_running(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    async def _check_challenges(self) -> None:
        """Scan current page DOM and title for security challenge indicators."""
        if not self._page:
            return
        title = await self._page.title()
        content = await self._page.content()
        patterns = [
            r"captcha", r"cf-challenge", r"recaptcha", r"hcaptcha",
            r"access denied", r"security check", r"please verify you are a human"
        ]
        lowered = (title + " " + content[:2000]).lower()
        for pat in patterns:
            if re.search(pat, lowered):
                raise BrowserChallengeDetected(
                    f"Security barrier detected matching '{pat}'. Human intervention required."
                )

    async def navigate(self, url: str, timeout: float = 30.0) -> dict[str, Any]:
        if not await self.is_running():
            await self.start()
        try:
            response = await self._page.goto(url, timeout=timeout * 1000)
            await self._check_challenges()
            return {
                "url": self._page.url,
                "title": await self._page.title(),
                "status_code": response.status if response else 200,
            }
        except TimeoutError:
            raise TimeoutError(f"Navigation to '{url}' timed out after {timeout}s")

    async def get_url_and_title(self) -> dict[str, str]:
        if not await self.is_running():
            return {"url": "about:blank", "title": ""}
        return {
            "url": self._page.url,
            "title": await self._page.title(),
        }

    async def extract_text(self, selector: Optional[str] = None, max_chars: int = 5000) -> str:
        if not await self.is_running():
            return ""
        if selector:
            element = await self._page.wait_for_selector(selector)
            text = (await element.inner_text()) if element else ""
        else:
            text = await self._page.inner_text("body")
        return (text or "")[:max_chars]

    async def click(self, selector: str, timeout: float = 15.0) -> dict[str, Any]:
        if not await self.is_running():
            raise BrowserDriverError("Browser session not started")
        await self._page.click(selector, timeout=timeout * 1000)
        await self._check_challenges()
        return {"clicked": selector}

    async def type_text(
        self, selector: str, text: str, clear_first: bool = True, timeout: float = 15.0
    ) -> dict[str, Any]:
        if not await self.is_running():
            raise BrowserDriverError("Browser session not started")
        if clear_first:
            await self._page.fill(selector, "", timeout=timeout * 1000)
        await self._page.type(selector, text, timeout=timeout * 1000)
        return {"selector": selector, "entered_chars": len(text)}

    async def capture_screenshot(self) -> bytes:
        if not await self.is_running():
            raise BrowserDriverError("Browser session not started")
        return await self._page.screenshot(type="png", full_page=False)

    async def inspect_page(self) -> dict[str, Any]:
        if not await self.is_running():
            return {"status": "inactive"}
        return {
            "url": self._page.url,
            "title": await self._page.title(),
            "text_excerpt": (await self.extract_text(max_chars=500)),
        }
