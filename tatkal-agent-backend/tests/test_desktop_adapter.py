"""
Tests for the DesktopToolAdapter and MockDesktopDriver.

Verifies input validation, mock operations, unsupported environment handling,
permission denial detection, and graceful disabling.
"""

from __future__ import annotations

import pytest

from app.integrations.contracts import ToolAction, ToolActionStatus
from app.tools.artifacts import ArtifactManager
from app.tools.desktop.adapter import DesktopToolAdapter
from app.tools.desktop.driver import MockDesktopDriver


@pytest.fixture
def artifact_manager(tmp_path):
    return ArtifactManager(base_dir=str(tmp_path))


@pytest.fixture
def mock_driver():
    return MockDesktopDriver(supported=True, has_permissions=True)


@pytest.fixture
def desktop_adapter(mock_driver, artifact_manager):
    return DesktopToolAdapter(
        driver=mock_driver,
        artifact_manager=artifact_manager,
        is_available=True,
    )


class TestDesktopAdapterValidation:
    """Verify input validation on desktop actions."""

    @pytest.mark.asyncio
    async def test_click_requires_coordinates(self, desktop_adapter):
        res1 = await desktop_adapter.execute(ToolAction(action_type="click", parameters={}))
        assert res1.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "x" in res1.error_message and "y" in res1.error_message

        res2 = await desktop_adapter.execute(ToolAction(action_type="click", parameters={"x": -5, "y": 10}))
        assert res2.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "negative" in res2.error_message

    @pytest.mark.asyncio
    async def test_type_text_requires_text(self, desktop_adapter):
        res = await desktop_adapter.execute(ToolAction(action_type="type_text", parameters={}))
        assert res.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "text" in res.error_message

    @pytest.mark.asyncio
    async def test_press_key_requires_key(self, desktop_adapter):
        res = await desktop_adapter.execute(ToolAction(action_type="press_key", parameters={}))
        assert res.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "key" in res.error_message


class TestDesktopAdapterExecution:
    """Verify mock desktop interactions."""

    @pytest.mark.asyncio
    async def test_session_status(self, desktop_adapter):
        res = await desktop_adapter.execute(ToolAction(action_type="session_status"))
        assert res.status == ToolActionStatus.SUCCESS
        assert res.output["supported"] is True
        assert res.output["status"] == "ready"

    @pytest.mark.asyncio
    async def test_click_and_type(self, desktop_adapter):
        click_res = await desktop_adapter.execute(
            ToolAction(action_type="click", parameters={"x": 100, "y": 200})
        )
        assert click_res.status == ToolActionStatus.SUCCESS
        assert click_res.output == {"action": "click", "x": 100, "y": 200}

        type_res = await desktop_adapter.execute(
            ToolAction(action_type="type_text", parameters={"text": "hello desktop"})
        )
        assert type_res.status == ToolActionStatus.SUCCESS
        assert type_res.output["chars"] == 13

        key_res = await desktop_adapter.execute(
            ToolAction(action_type="press_key", parameters={"key": "enter"})
        )
        assert key_res.status == ToolActionStatus.SUCCESS
        assert key_res.output == {"action": "press_key", "key": "enter"}

    @pytest.mark.asyncio
    async def test_screenshot_artifact_creation(self, desktop_adapter, artifact_manager):
        res = await desktop_adapter.execute(
            ToolAction(action_type="screenshot", parameters={"run_id": "desktop-run-1"})
        )
        assert res.status == ToolActionStatus.SUCCESS
        ref = res.output["artifact_ref"]
        assert ref.startswith("artifact://screenshots/desktop_")

        path = artifact_manager.resolve_reference(ref)
        assert path.exists()


class TestDesktopEnvironmentAndPermissions:
    """Verify environment restrictions and permission denial handling."""

    @pytest.mark.asyncio
    async def test_disabled_adapter_returns_unavailable(self, mock_driver, artifact_manager):
        disabled_adapter = DesktopToolAdapter(
            driver=mock_driver,
            artifact_manager=artifact_manager,
            is_available=False,
        )
        res = await disabled_adapter.execute(ToolAction(action_type="session_status"))
        assert res.status == ToolActionStatus.TOOL_UNAVAILABLE
        assert "unavailable" in res.error_message

    @pytest.mark.asyncio
    async def test_unsupported_environment_returns_unavailable(self, desktop_adapter, mock_driver):
        mock_driver.set_environment(supported=False, has_permissions=False)
        res = await desktop_adapter.execute(
            ToolAction(action_type="click", parameters={"x": 50, "y": 50})
        )
        assert res.status == ToolActionStatus.TOOL_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_permission_denial_triggers_human_intervention(self, desktop_adapter, mock_driver):
        mock_driver.set_environment(supported=True, has_permissions=False)
        res = await desktop_adapter.execute(
            ToolAction(action_type="click", parameters={"x": 50, "y": 50})
        )
        assert res.status == ToolActionStatus.HUMAN_INTERVENTION_REQUIRED
        assert "permission" in res.error_message.lower()
