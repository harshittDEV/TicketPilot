"""
Tests for Tool Adapter Architecture, IntegrationRegistry tool extensions,
BaseToolAdapter, and ArtifactManager.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import IntegrationNotRegisteredError, ResourceConflictError
from app.integrations.contracts import (
    ToolAction,
    ToolActionStatus,
    ToolExecutionResult,
    ToolMetadata,
)
from app.integrations.registry import IntegrationRegistry
from app.tools.artifacts import (
    ArtifactManager,
    ArtifactNotFoundError,
    ArtifactSizeLimitExceededError,
)
from app.tools.base import BaseToolAdapter


class DummyTool(BaseToolAdapter):
    """Simple test tool adapter."""

    def __init__(self, name: str = "dummy", *, is_available: bool = True) -> None:
        super().__init__(
            name=name,
            description="Dummy tool for testing",
            version="1.0.0",
            capabilities=["echo", "fail", "slow", "need_human"],
            is_available=is_available,
        )

    async def _dispatch(self, action: ToolAction) -> ToolExecutionResult:
        if action.action_type == "echo":
            return ToolExecutionResult(
                status=ToolActionStatus.SUCCESS,
                output=action.parameters,
            )
        if action.action_type == "fail":
            return ToolExecutionResult(
                status=ToolActionStatus.RECOVERABLE_FAILURE,
                error_message="Simulated recoverable failure",
            )
        if action.action_type == "slow":
            raise TimeoutError("Simulated timeout in dummy tool")
        if action.action_type == "need_human":
            return ToolExecutionResult(
                status=ToolActionStatus.HUMAN_INTERVENTION_REQUIRED,
                error_message="Requires user input",
            )
        return ToolExecutionResult(
            status=ToolActionStatus.INVALID_ARGUMENTS,
            error_message=f"Unsupported action: {action.action_type}",
        )


class TestToolRegistry:
    """Verify tool registration, lookup, duplicate handling, and health."""

    def test_register_and_lookup_tool(self):
        registry = IntegrationRegistry()
        tool = DummyTool("search")
        registry.register_tool("search", tool)

        assert registry.is_tool_registered("search") is True
        assert registry.is_tool_registered("tool:search") is True
        assert registry.get_tool("search") is tool
        assert registry.get_tool("tool:search") is tool

    def test_duplicate_registration_rejected(self):
        registry = IntegrationRegistry()
        registry.register_tool("search", DummyTool("search"))
        with pytest.raises(ResourceConflictError):
            registry.register_tool("search", DummyTool("search"))

    def test_duplicate_registration_force_allowed(self):
        registry = IntegrationRegistry()
        tool1 = DummyTool("search")
        tool2 = DummyTool("search")
        registry.register_tool("search", tool1)
        registry.register_tool("search", tool2, force=True)
        assert registry.get_tool("search") is tool2

    def test_lookup_missing_tool_raises(self):
        registry = IntegrationRegistry()
        with pytest.raises(IntegrationNotRegisteredError):
            registry.get_tool("nonexistent")

    def test_list_tools_returns_metadata(self):
        registry = IntegrationRegistry()
        t1 = DummyTool("tool_a")
        t2 = DummyTool("tool_b", is_available=False)
        registry.register_tool("tool_a", t1)
        registry.register_tool("tool_b", t2)

        meta_list = registry.list_tools()
        names = [m.name for m in meta_list]
        assert "tool_a" in names
        assert "tool_b" in names

        tool_b_meta = next(m for m in meta_list if m.name == "tool_b")
        assert tool_b_meta.is_available is False

    @pytest.mark.asyncio
    async def test_tool_health_check(self):
        registry = IntegrationRegistry()
        healthy_tool = DummyTool("healthy", is_available=True)
        unhealthy_tool = DummyTool("unhealthy", is_available=False)
        registry.register_tool("healthy", healthy_tool)
        registry.register_tool("unhealthy", unhealthy_tool)

        res_healthy = await registry.check_tool_health("healthy")
        assert res_healthy["healthy"] is True
        assert res_healthy["status"] == "healthy"

        res_unhealthy = await registry.check_tool_health("unhealthy")
        assert res_unhealthy["healthy"] is False


class TestBaseToolAdapter:
    """Verify BaseToolAdapter validation, timing, and error handling."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        tool = DummyTool()
        action = ToolAction(action_type="echo", parameters={"msg": "hello"})
        res = await tool.execute(action)
        assert res.status == ToolActionStatus.SUCCESS
        assert res.output == {"msg": "hello"}
        assert res.duration_seconds is not None
        assert res.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_execute_unsupported_action(self):
        tool = DummyTool()
        action = ToolAction(action_type="unsupported_action")
        res = await tool.execute(action)
        assert res.status == ToolActionStatus.INVALID_ARGUMENTS
        assert "not supported" in res.error_message

    @pytest.mark.asyncio
    async def test_execute_when_tool_unavailable(self):
        tool = DummyTool(is_available=False)
        action = ToolAction(action_type="echo")
        res = await tool.execute(action)
        assert res.status == ToolActionStatus.TOOL_UNAVAILABLE
        assert "unavailable" in res.error_message

    @pytest.mark.asyncio
    async def test_execute_timeout_handling(self):
        tool = DummyTool()
        action = ToolAction(action_type="slow")
        res = await tool.execute(action)
        assert res.status == ToolActionStatus.TIMEOUT
        assert "timed out" in res.error_message

    @pytest.mark.asyncio
    async def test_execute_human_intervention_required(self):
        tool = DummyTool()
        action = ToolAction(action_type="need_human")
        res = await tool.execute(action)
        assert res.status == ToolActionStatus.HUMAN_INTERVENTION_REQUIRED


class TestArtifactManager:
    """Verify artifact persistence, naming, size bounds, and path traversal guards."""

    def test_save_and_resolve_screenshot(self, tmp_path):
        mgr = ArtifactManager(base_dir=str(tmp_path), max_size_bytes=10000)
        data = b"\x89PNG\r\n\x1a\nfakeimage"
        ref = mgr.save_screenshot(data, prefix="test", run_id="run-12345678")

        assert ref.startswith("artifact://screenshots/test_run-1234_")
        resolved_path = mgr.resolve_reference(ref)
        assert resolved_path.exists()
        assert resolved_path.read_bytes() == data

    def test_save_screenshot_exceeds_limit(self, tmp_path):
        mgr = ArtifactManager(base_dir=str(tmp_path), max_size_bytes=50)
        huge_data = b"X" * 100
        with pytest.raises(ArtifactSizeLimitExceededError):
            mgr.save_screenshot(huge_data)

    def test_resolve_invalid_or_nonexistent_reference(self, tmp_path):
        mgr = ArtifactManager(base_dir=str(tmp_path))
        with pytest.raises(ArtifactNotFoundError):
            mgr.resolve_reference("artifact://screenshots/does_not_exist.png")

    def test_directory_traversal_attack_blocked(self, tmp_path):
        mgr = ArtifactManager(base_dir=str(tmp_path))
        with pytest.raises(ArtifactNotFoundError):
            mgr.resolve_reference("artifact://../../etc/passwd")

    def test_list_artifacts(self, tmp_path):
        mgr = ArtifactManager(base_dir=str(tmp_path))
        mgr.save_screenshot(b"img1", prefix="screen1")
        mgr.save_screenshot(b"img2", prefix="screen2")

        listed = mgr.list_artifacts("screenshots")
        assert len(listed) == 2
        refs = [item["ref"] for item in listed]
        assert any("screen1" in r for r in refs)
        assert any("screen2" in r for r in refs)
