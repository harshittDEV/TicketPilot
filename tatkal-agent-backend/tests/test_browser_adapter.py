"""
Tests for the BrowserToolAdapter and MockBrowserDriver.

Ensures zero live browser dependencies, strict input validation,
screenshot artifact generation, timeout management, and human
intervention triggering on CAPTCHA / authentication walls.
"""

from __future__ import annotations

import pytest

from app.integrations.contracts import ToolAction, ToolActionStatus
from app.tools.artifacts import ArtifactManager
from app.tools.browser.adapter import BrowserToolAdapter
from app.tools.browser.driver import MockBrowserDriver


@pytest.fixture
def artifact_manager(tmp_path):
    return ArtifactManager(base_dir=str(tmp_path))


@pytest.fixture
def mock_driver():
    return MockBrowserDriver()


@pytest.fixture
def browser_adapter(mock_driver, artifact_manager):
    return BrowserToolAdapter(driver=mock_driver, artifact_manager=artifact_manager)


class TestBrowserAdapterValidation:
    """Verify input validation on browser actions."""

    @pytest.mark.asyncio
    async def test_navigate_requires_url(self, browser_adapter):
        action = ToolAction(action_type="navigate", parameters={})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "url" in res.error_message

    @pytest.mark.asyncio
    async def test_navigate_rejects_unsafe_scheme(self, browser_adapter):
        action = ToolAction(action_type="navigate", parameters={"url": "javascript:alert(1)"})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "scheme" in res.error_message

    @pytest.mark.asyncio
    async def test_click_requires_selector(self, browser_adapter):
        action = ToolAction(action_type="click", parameters={})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "selector" in res.error_message

    @pytest.mark.asyncio
    async def test_type_text_requires_selector_and_text(self, browser_adapter):
        action1 = ToolAction(action_type="type_text", parameters={"selector": "#btn"})
        res1 = await browser_adapter.execute(action1)
        assert res1.status == ToolActionStatus.INVALID_ARGUMENTS

        action2 = ToolAction(action_type="type_text", parameters={"text": "hello"})
        res2 = await browser_adapter.execute(action2)
        assert res2.status == ToolActionStatus.INVALID_ARGUMENTS


class TestBrowserAdapterExecution:
    """Verify standard browser capabilities via mock driver."""

    @pytest.mark.asyncio
    async def test_successful_navigation(self, browser_adapter):
        action = ToolAction(action_type="navigate", parameters={"url": "https://example.com/test"})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.SUCCESS
        assert res.output["url"] == "https://example.com/test"
        assert res.output["status_code"] == 200

    @pytest.mark.asyncio
    async def test_get_url_and_title(self, browser_adapter, mock_driver):
        mock_driver.set_page("https://example.com/home", "Home Page", "Welcome")
        action = ToolAction(action_type="get_url_and_title")
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.SUCCESS
        assert res.output["title"] == "Home Page"
        assert res.output["url"] == "https://example.com/home"

    @pytest.mark.asyncio
    async def test_extract_text_bounded(self, browser_adapter, mock_driver):
        long_content = "A" * 2000
        mock_driver.set_page("https://example.com", "Test", long_content)

        action = ToolAction(action_type="extract_text", parameters={"max_chars": 50})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.SUCCESS
        assert len(res.output["text"]) == 50

    @pytest.mark.asyncio
    async def test_click_and_type(self, browser_adapter):
        click_action = ToolAction(action_type="click", parameters={"selector": "#submit-btn"})
        res_click = await browser_adapter.execute(click_action)
        assert res_click.status == ToolActionStatus.SUCCESS
        assert res_click.output["clicked"] == "#submit-btn"

        type_action = ToolAction(
            action_type="type_text",
            parameters={"selector": "#username", "text": "john_doe"},
        )
        res_type = await browser_adapter.execute(type_action)
        assert res_type.status == ToolActionStatus.SUCCESS
        assert res_type.output["entered_chars"] == 8

    @pytest.mark.asyncio
    async def test_screenshot_captures_artifact(self, browser_adapter, artifact_manager):
        await browser_adapter.driver.start()
        action = ToolAction(action_type="screenshot", parameters={"run_id": "run-test-999"})
        res = await browser_adapter.execute(action)

        assert res.status == ToolActionStatus.SUCCESS
        ref = res.output["artifact_ref"]
        assert ref.startswith("artifact://screenshots/")
        # File should be retrievable from artifact manager
        resolved = artifact_manager.resolve_reference(ref)
        assert resolved.exists()
        assert len(resolved.read_bytes()) > 0

    @pytest.mark.asyncio
    async def test_health_check(self, browser_adapter):
        action = ToolAction(action_type="health")
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.SUCCESS
        assert res.output["healthy"] is True


class TestBrowserChallengesAndErrors:
    """Verify challenge detection, timeouts, and recoverable failures."""

    @pytest.mark.asyncio
    async def test_captcha_detection_triggers_human_intervention(self, browser_adapter):
        action = ToolAction(action_type="navigate", parameters={"url": "https://example.com/captcha-check"})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.HUMAN_INTERVENTION_REQUIRED
        assert "CAPTCHA" in res.error_message

    @pytest.mark.asyncio
    async def test_auth_wall_triggers_human_intervention(self, browser_adapter):
        action = ToolAction(action_type="navigate", parameters={"url": "https://example.com/signin-portal"})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.HUMAN_INTERVENTION_REQUIRED
        assert "Authentication challenge" in res.error_message

    @pytest.mark.asyncio
    async def test_timeout_returns_structured_timeout(self, browser_adapter, mock_driver):
        mock_driver.set_faults(timeout=True)
        action = ToolAction(action_type="navigate", parameters={"url": "https://example.com"})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.TIMEOUT
        assert "timed out" in res.error_message

    @pytest.mark.asyncio
    async def test_driver_error_returns_recoverable_failure(self, browser_adapter, mock_driver):
        mock_driver.set_faults(fail=True, message="DNS lookup failed")
        action = ToolAction(action_type="navigate", parameters={"url": "https://example.com"})
        res = await browser_adapter.execute(action)
        assert res.status == ToolActionStatus.RECOVERABLE_FAILURE
        assert "DNS lookup failed" in res.error_message
