"""
Tests for Skill Definition Loading and Skill Execution Engine.

Verifies declarative YAML parsing, schema validation, input validation,
tool resolution, step-by-step execution, failure stops, cancellation,
and human intervention handling.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from app.agent.models import ExecutionContext
from app.agent.tool_executor import ToolExecutor
from app.integrations.contracts import (
    ToolAction,
    ToolActionStatus,
    ToolExecutionResult,
    ToolMetadata,
)
from app.integrations.registry import IntegrationRegistry
from app.skills.executor import SkillExecutionError, SkillExecutor
from app.skills.loader import (
    DuplicateSkillError,
    SkillLoader,
    SkillNotFoundError,
    SkillValidationError,
)
from app.skills.models import SkillDefinition, SkillInput, SkillStep
from app.tools.base import BaseToolAdapter


class MockSkillTool(BaseToolAdapter):
    """Tool adapter used for testing skills."""

    def __init__(self, name: str = "mock_tool", *, is_available: bool = True) -> None:
        super().__init__(
            name=name,
            description="Mock tool for skill testing",
            version="1.0.0",
            capabilities=["step1", "step2", "step3", "challenge_step", "failing_step"],
            is_available=is_available,
        )
        self.dispatched_actions: list[ToolAction] = []

    async def _dispatch(self, action: ToolAction) -> ToolExecutionResult:
        self.dispatched_actions.append(action)
        act = action.action_type
        if act == "challenge_step":
            return ToolExecutionResult(
                status=ToolActionStatus.HUMAN_INTERVENTION_REQUIRED,
                error_message="Security challenge requires human input",
            )
        if act == "failing_step":
            return ToolExecutionResult(
                status=ToolActionStatus.FAILURE,
                error_message="Step failed deliberately",
            )
        return ToolExecutionResult(
            status=ToolActionStatus.SUCCESS,
            output={"processed": act, "params": action.parameters},
        )


class TestSkillLoader:
    """Verify loading, duplicate detection, and schema validation."""

    def test_load_browser_inspection_skill(self):
        loader = SkillLoader()
        skills = loader.load_all()
        assert "browser_inspection" in skills
        skill = loader.get_skill("browser_inspection")
        assert skill.name == "browser_inspection"
        assert len(skill.steps) == 4
        assert "browser" in skill.allowed_tools

    def test_missing_skill_raises_error(self):
        loader = SkillLoader()
        with pytest.raises(SkillNotFoundError):
            loader.get_skill("nonexistent_skill_xyz")

    def test_malformed_yaml_raises_validation_error(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("name: 123\nsteps: not_a_list\n", encoding="utf-8")

        loader = SkillLoader(definitions_dir=tmp_path)
        with pytest.raises(SkillValidationError):
            loader.load_all()

    def test_duplicate_skill_name_raises_error(self, tmp_path):
        f1 = tmp_path / "skill1.yaml"
        f2 = tmp_path / "skill2.yaml"
        content = (
            "name: duplicate_skill\n"
            "description: First\n"
            "steps: []\n"
        )
        f1.write_text(content, encoding="utf-8")
        f2.write_text(content, encoding="utf-8")

        loader = SkillLoader(definitions_dir=tmp_path)
        with pytest.raises(DuplicateSkillError):
            loader.load_all()


class TestSkillExecutor:
    """Verify skill input validation, tool verification, and step execution."""

    @pytest.fixture
    def setup_skill_env(self, tmp_path):
        # Create a simple test skill
        skill_content = {
            "name": "test_workflow",
            "description": "Multi-step test skill",
            "required_inputs": [
                {"name": "target_url", "type": "string", "required": True},
                {"name": "tag", "type": "string", "required": False, "default": "default_tag"},
            ],
            "allowed_tools": ["mock_tool"],
            "steps": [
                {
                    "step_id": "s1",
                    "tool_name": "mock_tool",
                    "action_type": "step1",
                    "parameters": {"url": "{{ inputs.target_url }}"},
                },
                {
                    "step_id": "s2",
                    "tool_name": "mock_tool",
                    "action_type": "step2",
                    "parameters": {"tag": "{{ inputs.tag }}"},
                },
            ],
        }
        skill_file = tmp_path / "test_workflow.yaml"
        skill_file.write_text(yaml.safe_dump(skill_content), encoding="utf-8")

        loader = SkillLoader(definitions_dir=tmp_path)
        registry = IntegrationRegistry()
        tool = MockSkillTool("mock_tool")
        registry.register_tool("mock_tool", tool)
        tool_executor = ToolExecutor(registry)
        executor = SkillExecutor(loader=loader, tool_executor=tool_executor, registry=registry)

        return executor, tool, loader, registry

    @pytest.mark.asyncio
    async def test_successful_skill_execution(self, setup_skill_env):
        executor, tool, _, _ = setup_skill_env
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="skill")

        result = await executor.execute_skill(
            "test_workflow",
            inputs={"target_url": "https://example.com/api"},
            context=ctx,
        )

        assert result.success is True
        assert result.status == "completed"
        assert result.steps_completed == 2
        assert len(result.step_results) == 2

        # Verify parameter interpolation
        assert tool.dispatched_actions[0].parameters["url"] == "https://example.com/api"
        assert tool.dispatched_actions[1].parameters["tag"] == "default_tag"

    @pytest.mark.asyncio
    async def test_missing_required_input_raises_error(self, setup_skill_env):
        executor, _, _, _ = setup_skill_env
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="skill")

        with pytest.raises(ValueError) as exc:
            await executor.execute_skill("test_workflow", inputs={}, context=ctx)
        assert "target_url" in str(exc.value)

    @pytest.mark.asyncio
    async def test_missing_allowed_tool_raises_error(self, setup_skill_env):
        executor, _, _, registry = setup_skill_env
        registry.clear()  # Remove mock_tool
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="skill")

        with pytest.raises(SkillExecutionError) as exc:
            await executor.execute_skill(
                "test_workflow",
                inputs={"target_url": "https://example.com"},
                context=ctx,
            )
        assert "mock_tool" in str(exc.value)

    @pytest.mark.asyncio
    async def test_step_failure_stops_execution(self, tmp_path):
        skill_content = {
            "name": "fail_workflow",
            "allowed_tools": ["mock_tool"],
            "steps": [
                {"step_id": "step_fail", "tool_name": "mock_tool", "action_type": "failing_step"},
                {"step_id": "step_never", "tool_name": "mock_tool", "action_type": "step1"},
            ],
        }
        (tmp_path / "fail.yaml").write_text(yaml.safe_dump(skill_content), encoding="utf-8")

        loader = SkillLoader(definitions_dir=tmp_path)
        registry = IntegrationRegistry()
        tool = MockSkillTool("mock_tool")
        registry.register_tool("mock_tool", tool)
        executor = SkillExecutor(loader, ToolExecutor(registry), registry)
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="skill")

        res = await executor.execute_skill("fail_workflow", inputs={}, context=ctx)
        assert res.success is False
        assert res.status == "failed"
        assert res.steps_completed == 0
        assert "failed" in res.error_message
        assert len(tool.dispatched_actions) == 1  # Second step was never called!

    @pytest.mark.asyncio
    async def test_cancellation_halts_workflow(self, setup_skill_env):
        executor, _, _, _ = setup_skill_env
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="skill")
        ctx.mark_cancelled()

        res = await executor.execute_skill(
            "test_workflow",
            inputs={"target_url": "https://example.com"},
            context=ctx,
        )
        assert res.success is False
        assert res.status == "cancelled"

    @pytest.mark.asyncio
    async def test_human_checkpoint_step_triggers_waiting_for_human(self, tmp_path):
        skill_content = {
            "name": "human_workflow",
            "allowed_tools": ["mock_tool"],
            "steps": [
                {
                    "step_id": "payment_approval",
                    "tool_name": "mock_tool",
                    "action_type": "step1",
                    "require_human": True,
                    "description": "User must approve transaction amount",
                }
            ],
        }
        (tmp_path / "human.yaml").write_text(yaml.safe_dump(skill_content), encoding="utf-8")

        loader = SkillLoader(definitions_dir=tmp_path)
        registry = IntegrationRegistry()
        tool = MockSkillTool("mock_tool")
        registry.register_tool("mock_tool", tool)
        executor = SkillExecutor(loader, ToolExecutor(registry), registry)
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="skill")

        res = await executor.execute_skill("human_workflow", inputs={}, context=ctx)
        assert res.status == "waiting_for_human"
        assert res.requires_human is True
        assert "approve" in res.human_intervention_details["description"]

    @pytest.mark.asyncio
    async def test_tool_reporting_challenge_triggers_waiting_for_human(self, tmp_path):
        skill_content = {
            "name": "challenge_workflow",
            "allowed_tools": ["mock_tool"],
            "steps": [
                {
                    "step_id": "detect_captcha",
                    "tool_name": "mock_tool",
                    "action_type": "challenge_step",
                }
            ],
        }
        (tmp_path / "challenge.yaml").write_text(yaml.safe_dump(skill_content), encoding="utf-8")

        loader = SkillLoader(definitions_dir=tmp_path)
        registry = IntegrationRegistry()
        tool = MockSkillTool("mock_tool")
        registry.register_tool("mock_tool", tool)
        executor = SkillExecutor(loader, ToolExecutor(registry), registry)
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="skill")

        res = await executor.execute_skill("challenge_workflow", inputs={}, context=ctx)
        assert res.status == "waiting_for_human"
        assert res.requires_human is True
        assert "challenge" in res.human_intervention_details["error"].lower()
