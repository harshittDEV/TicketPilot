"""
Tests for Skill & Orchestrator Integration with Tools, Observer, and Verifier.

Tests the complete demonstration workflow using browser_inspection.yaml,
verifying that observations, screenshot artifacts, and step results are
properly assembled without live network or external browser requirements.
"""

from __future__ import annotations

import pytest

from app.agent.models import ExecutionContext
from app.agent.observer import DefaultObserver
from app.agent.tool_executor import ToolExecutor
from app.agent.verifier import AlwaysFailVerifier, DeterministicVerifier
from app.integrations.registry import IntegrationRegistry
from app.skills.executor import SkillExecutor
from app.skills.loader import SkillLoader
from app.tools.artifacts import ArtifactManager
from app.tools.browser.adapter import BrowserToolAdapter
from app.tools.browser.driver import MockBrowserDriver


@pytest.fixture
def test_env(tmp_path):
    artifact_mgr = ArtifactManager(base_dir=str(tmp_path / "artifacts"))
    mock_driver = MockBrowserDriver()
    mock_driver.set_page(
        "https://example.com",
        "Example Domain",
        "This domain is for use in illustrative examples in documents.",
    )

    browser = BrowserToolAdapter(driver=mock_driver, artifact_manager=artifact_mgr)
    registry = IntegrationRegistry()
    registry.register_tool("browser", browser)

    tool_executor = ToolExecutor(registry)
    observer = DefaultObserver(registry, capture_screenshots=True)
    verifier = DeterministicVerifier()
    loader = SkillLoader()  # Uses default definitions directory including browser_inspection.yaml

    executor = SkillExecutor(
        loader=loader,
        tool_executor=tool_executor,
        registry=registry,
        observer=observer,
        verifier=verifier,
    )

    return {
        "executor": executor,
        "browser": browser,
        "driver": mock_driver,
        "artifact_mgr": artifact_mgr,
        "observer": observer,
        "registry": registry,
    }


class TestSkillOrchestrationIntegration:
    """Verify end-to-end skill workflow execution with browser adapter."""

    @pytest.mark.asyncio
    async def test_browser_inspection_demonstration_skill(self, test_env):
        executor = test_env["executor"]
        artifact_mgr = test_env["artifact_mgr"]
        ctx = ExecutionContext(task_id="task-demo-1", run_id="run-demo-1", task_type="skill")

        result = await executor.execute_skill(
            "browser_inspection",
            inputs={"test_url": "https://example.com"},
            context=ctx,
        )

        assert result.success is True
        assert result.status == "completed"
        assert result.steps_completed == 4
        assert len(result.step_results) == 4

        # Step 1: Navigation
        s1 = result.step_results[0]
        assert s1.step_id == "step_1_navigate"
        assert s1.success is True
        assert s1.output["url"] == "https://example.com"

        # Step 2: URL and Title
        s2 = result.step_results[1]
        assert s2.step_id == "step_2_get_url_and_title"
        assert s2.output["title"] == "Example Domain"

        # Step 3: Text extraction
        s3 = result.step_results[2]
        assert s3.step_id == "step_3_extract_text"
        assert "illustrative examples" in s3.output["text"]

        # Step 4: Screenshot artifact
        s4 = result.step_results[3]
        assert s4.step_id == "step_4_screenshot"
        screenshot_ref = s4.output["artifact_ref"]
        assert screenshot_ref.startswith("artifact://screenshots/browser_")

        # Verify artifact exists on disk
        saved_file = artifact_mgr.resolve_reference(screenshot_ref)
        assert saved_file.exists()
        assert len(saved_file.read_bytes()) > 0

    @pytest.mark.asyncio
    async def test_default_observer_captures_browser_state(self, test_env):
        observer = test_env["observer"]
        browser = test_env["browser"]
        ctx = ExecutionContext(task_id="task-1", run_id="run-1", task_type="browser_task")

        # Navigate browser first
        from app.integrations.contracts import ToolAction
        await browser.execute(ToolAction(action_type="navigate", parameters={"url": "https://example.com"}))

        obs = await observer.observe(ctx)
        assert obs.source == "browser"
        assert obs.url == "https://example.com"
        assert obs.title == "Example Domain"
        assert "illustrative examples" in obs.text_excerpt
        assert obs.artifact_ref is not None  # capture_screenshots=True
