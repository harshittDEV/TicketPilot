"""
Tests for the agent orchestrator, LLM abstraction, tool executor,
observer, and verifier.

Uses fake planners, fake tools, fake observers, and deterministic
verifiers.  No real LLM credentials or browser sessions required.
"""

import pytest
import asyncio

from app.agent.errors import (
    PlannerError,
    ToolResolutionError,
)
from app.agent.llm.base import (
    BaseLLMClient,
    FakePlanner,
    LLMRequest,
    LLMResponse,
)
from app.agent.models import (
    ActionType,
    ExecutionContext,
    Observation,
    PlannerRequest,
    PlannerResponse,
    ToolResult,
    VerificationResult,
)
from app.agent.observer import FakeObserver
from app.agent.orchestrator import Orchestrator, OrchestratorResult
from app.agent.tool_executor import ToolExecutor
from app.agent.verifier import AlwaysFailVerifier, DeterministicVerifier
from app.integrations.contracts import (
    AgentToolIntegration,
    ToolAction,
    ToolActionStatus,
    ToolExecutionResult,
    ToolMetadata,
)
from app.integrations.registry import IntegrationRegistry


# ═══════════════════════════════════════════════════════════════════
# FAKE TOOL ADAPTER
# ═══════════════════════════════════════════════════════════════════

class FakeToolAdapter:
    """Fake tool adapter implementing AgentToolIntegration for tests."""

    def __init__(
        self,
        *,
        succeed: bool = True,
        output: object = None,
        raise_on_execute: Exception | None = None,
        delay_seconds: float = 0.0,
    ):
        self._succeed = succeed
        self._output = output
        self._raise = raise_on_execute
        self._delay = delay_seconds
        self.call_count = 0

    async def execute(self, action: ToolAction) -> ToolExecutionResult:
        self.call_count += 1
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._raise:
            raise self._raise
        status = ToolActionStatus.SUCCESS if self._succeed else ToolActionStatus.FAILURE
        return ToolExecutionResult(
            status=status,
            output=self._output or {"result": "fake"},
            error_message=None if self._succeed else "Fake failure",
            duration_seconds=0.01,
        )

    async def health_check(self) -> bool:
        return True

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="fake_tool",
            description="Fake tool adapter for testing",
            capabilities=["fake_action"],
            is_available=True,
        )


class SlowToolAdapter:
    """Tool that takes too long — for timeout tests."""

    async def execute(self, action: ToolAction) -> ToolExecutionResult:
        await asyncio.sleep(10)  # Will be cancelled by timeout
        return ToolExecutionResult(status=ToolActionStatus.SUCCESS, output={})

    async def health_check(self) -> bool:
        return True

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="slow_tool",
            description="Slow tool for timeout tests",
            capabilities=["slow_action"],
            is_available=True,
        )


# ═══════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════

def _make_orchestrator(
    *,
    planner: BaseLLMClient | None = None,
    registry: IntegrationRegistry | None = None,
    observer=None,
    verifier=None,
    max_steps: int = 100,
    max_run_duration_seconds: float = 3600.0,
) -> Orchestrator:
    """Build an Orchestrator with all dependencies."""
    reg = registry or IntegrationRegistry()
    return Orchestrator(
        planner=planner or FakePlanner(),
        tool_executor=ToolExecutor(reg),
        observer=observer or FakeObserver(),
        verifier=verifier or DeterministicVerifier(),
        max_steps=max_steps,
        max_run_duration_seconds=max_run_duration_seconds,
    )


# ═══════════════════════════════════════════════════════════════════
# LLM ABSTRACTION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestFakePlanner:
    """Test the FakePlanner (deterministic LLM substitute)."""

    @pytest.mark.asyncio
    async def test_returns_complete_by_default(self):
        planner = FakePlanner()
        req = LLMRequest(
            planner_request=PlannerRequest(task_type="test"),
        )
        resp = await planner.plan(req)
        assert resp.planner_response.action_type == ActionType.COMPLETE
        assert resp.provider == "fake"

    @pytest.mark.asyncio
    async def test_returns_preconfigured_responses(self):
        responses = [
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="browser",
                reason="Navigate",
            ),
            PlannerResponse(
                action_type=ActionType.COMPLETE,
                reason="Done",
                task_complete=True,
            ),
        ]
        planner = FakePlanner(responses=responses)
        req = LLMRequest(planner_request=PlannerRequest(task_type="test"))

        r1 = await planner.plan(req)
        assert r1.planner_response.action_type == ActionType.TOOL_ACTION

        r2 = await planner.plan(req)
        assert r2.planner_response.action_type == ActionType.COMPLETE

    @pytest.mark.asyncio
    async def test_fail_after_n_calls(self):
        planner = FakePlanner(
            fail_after=1,
            fail_with=PlannerError("Simulated failure"),
        )
        req = LLMRequest(planner_request=PlannerRequest(task_type="test"))

        # First call succeeds
        await planner.plan(req)

        # Second call fails
        with pytest.raises(PlannerError):
            await planner.plan(req)

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self):
        planner = FakePlanner()
        assert await planner.health_check() is True

    def test_provider_name(self):
        planner = FakePlanner()
        assert planner.provider_name == "fake"

    @pytest.mark.asyncio
    async def test_runs_without_api_key(self):
        """FakePlanner must work without any provider credentials."""
        planner = FakePlanner()
        req = LLMRequest(planner_request=PlannerRequest(task_type="test"))
        resp = await planner.plan(req)
        assert resp.planner_response is not None


# ═══════════════════════════════════════════════════════════════════
# PLANNER RESPONSE VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestPlannerResponseValidation:
    """Test that PlannerResponse validates correctly."""

    def test_valid_tool_action(self):
        resp = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            action_parameters={"url": "https://example.com"},
            reason="Navigate to site",
        )
        assert resp.action_type == ActionType.TOOL_ACTION
        assert resp.tool_name == "browser"

    def test_valid_complete_action(self):
        resp = PlannerResponse(
            action_type=ActionType.COMPLETE,
            reason="Task is done",
            task_complete=True,
        )
        assert resp.task_complete is True

    def test_invalid_action_type_rejected(self):
        with pytest.raises(ValueError):
            PlannerResponse(
                action_type="INVALID_TYPE",
                reason="Bad",
            )

    def test_reason_max_length(self):
        """Reason field should enforce max_length."""
        resp = PlannerResponse(
            action_type=ActionType.COMPLETE,
            reason="x" * 1000,  # At limit
        )
        assert len(resp.reason) == 1000


# ═══════════════════════════════════════════════════════════════════
# TOOL EXECUTOR TESTS
# ═══════════════════════════════════════════════════════════════════

class TestToolExecutor:
    """Test the generic tool execution engine."""

    @pytest.mark.asyncio
    async def test_execute_successful_tool(self):
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter(succeed=True))
        executor = ToolExecutor(registry)

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            reason="Test",
        )
        ctx = ExecutionContext(
            task_id="t1", run_id="r1", task_type="test",
        )
        result = await executor.execute(plan, ctx)
        assert result.success is True
        assert result.tool_name == "browser"

    @pytest.mark.asyncio
    async def test_execute_failing_tool(self):
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter(succeed=False))
        executor = ToolExecutor(registry)

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            reason="Test",
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        result = await executor.execute(plan, ctx)
        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_missing_tool_raises_resolution_error(self):
        registry = IntegrationRegistry()
        executor = ToolExecutor(registry)

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="nonexistent",
            reason="Test",
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        with pytest.raises(ToolResolutionError):
            executor.validate_action(plan, ctx)

    @pytest.mark.asyncio
    async def test_tool_timeout_handled(self):
        registry = IntegrationRegistry()
        registry.register("slow", SlowToolAdapter())
        executor = ToolExecutor(registry, default_timeout=0.1, max_timeout=0.5)

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="slow",
            reason="Test",
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        result = await executor.execute(plan, ctx)
        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_tool_exception_handled(self):
        registry = IntegrationRegistry()
        registry.register(
            "broken",
            FakeToolAdapter(raise_on_execute=RuntimeError("Boom")),
        )
        executor = ToolExecutor(registry)

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="broken",
            reason="Test",
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        result = await executor.execute(plan, ctx)
        assert result.success is False
        assert "Boom" in result.error_message

    @pytest.mark.asyncio
    async def test_non_tool_action_returns_synthetic_result(self):
        registry = IntegrationRegistry()
        executor = ToolExecutor(registry)

        plan = PlannerResponse(
            action_type=ActionType.OBSERVE,
            reason="Need observation",
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        result = await executor.execute(plan, ctx)
        assert result.success is True

    def test_action_limit_enforced(self):
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter())
        executor = ToolExecutor(registry)

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            reason="Test",
        )
        ctx = ExecutionContext(
            task_id="t1", run_id="r1", task_type="test",
            max_steps=5, action_count=5,
        )
        from app.agent.errors import ActionLimitExceededError
        with pytest.raises(ActionLimitExceededError):
            executor.validate_action(plan, ctx)


# ═══════════════════════════════════════════════════════════════════
# OBSERVATION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestObserver:
    """Test observation interface."""

    @pytest.mark.asyncio
    async def test_fake_observer_returns_observation(self):
        observer = FakeObserver()
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        obs = await observer.observe(ctx)
        assert obs.source == "fake_observer"
        assert obs.observation_id is not None
        assert obs.timestamp is not None

    @pytest.mark.asyncio
    async def test_fake_observer_returns_preconfigured(self):
        custom = Observation(source="custom", content={"page": "login"})
        observer = FakeObserver(observations=[custom])
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        obs = await observer.observe(ctx)
        assert obs.source == "custom"
        assert obs.content["page"] == "login"

    @pytest.mark.asyncio
    async def test_fake_observer_tracks_call_count(self):
        observer = FakeObserver()
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        await observer.observe(ctx)
        await observer.observe(ctx)
        assert observer.call_count == 2


# ═══════════════════════════════════════════════════════════════════
# VERIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════

class TestDeterministicVerifier:
    """Test deterministic verification."""

    @pytest.mark.asyncio
    async def test_success_when_tool_succeeds(self):
        verifier = DeterministicVerifier()
        action = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            reason="Test",
        )
        result = ToolResult(
            tool_name="browser", action_type="click", success=True,
        )
        vr = await verifier.verify(action, result, None, None, None)
        assert vr.success is True

    @pytest.mark.asyncio
    async def test_failure_when_tool_fails(self):
        verifier = DeterministicVerifier()
        action = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            reason="Test",
        )
        result = ToolResult(
            tool_name="browser", action_type="click", success=False,
            error_message="Click failed",
        )
        vr = await verifier.verify(action, result, None, None, None)
        assert vr.success is False
        assert vr.mismatch is not None

    @pytest.mark.asyncio
    async def test_lower_confidence_with_expected_result(self):
        verifier = DeterministicVerifier()
        action = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            reason="Test",
        )
        result = ToolResult(
            tool_name="browser", action_type="click", success=True,
        )
        vr = await verifier.verify(
            action, result, None, None, "Login page visible"
        )
        assert vr.success is True
        assert vr.confidence < 1.0  # Lower confidence for semantic check


class TestAlwaysFailVerifier:
    """Test the always-fail verifier helper."""

    @pytest.mark.asyncio
    async def test_always_reports_failure(self):
        verifier = AlwaysFailVerifier()
        action = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            reason="Test",
        )
        result = ToolResult(
            tool_name="browser", action_type="click", success=True,
        )
        vr = await verifier.verify(action, result, None, None, None)
        assert vr.success is False


# ═══════════════════════════════════════════════════════════════════
# ORCHESTRATOR TESTS
# ═══════════════════════════════════════════════════════════════════

class TestOrchestrator:
    """Test the generic agent orchestrator."""

    @pytest.mark.asyncio
    async def test_simple_successful_workflow(self):
        """Planner returns TOOL_ACTION then COMPLETE → run succeeds."""
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter(succeed=True))

        planner = FakePlanner(responses=[
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="browser",
                action_parameters={"action_type": "click"},
                reason="Click button",
                expected_result="Button clicked",
            ),
            PlannerResponse(
                action_type=ActionType.COMPLETE,
                reason="Task done",
                task_complete=True,
            ),
        ])

        orch = _make_orchestrator(
            planner=planner,
            registry=registry,
        )

        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "COMPLETED"
        assert result.steps_completed == 1
        assert len(result.step_records) == 2  # tool_action + complete

    @pytest.mark.asyncio
    async def test_orchestrator_order_plan_execute_observe_verify(self):
        """Verify the orchestrator follows the correct order."""
        registry = IntegrationRegistry()
        adapter = FakeToolAdapter(succeed=True)
        registry.register("browser", adapter)
        observer = FakeObserver()

        planner = FakePlanner(responses=[
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="browser",
                action_parameters={"action_type": "click"},
                reason="Step 1",
            ),
            PlannerResponse(
                action_type=ActionType.COMPLETE,
                reason="Done",
                task_complete=True,
            ),
        ])

        orch = _make_orchestrator(
            planner=planner,
            registry=registry,
            observer=observer,
        )

        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "COMPLETED"
        # Observer called: 1 initial + 1 post-action = 2
        assert observer.call_count == 2
        # Tool called once
        assert adapter.call_count == 1
        # Step record has observation IDs and verification
        step = result.step_records[0]
        assert step.observation_before is not None
        assert step.observation_after is not None
        assert step.verification is not None
        assert step.verification.success is True

    @pytest.mark.asyncio
    async def test_reject_malformed_planner_response(self):
        """TOOL_ACTION without tool_name triggers PlannerError."""

        class BadPlanner(BaseLLMClient):
            async def plan(self, request):
                return LLMResponse(
                    planner_response=PlannerResponse(
                        action_type=ActionType.TOOL_ACTION,
                        tool_name=None,  # missing!
                        reason="Bad plan",
                    ),
                    provider="bad",
                )
            async def health_check(self):
                return True
            @property
            def provider_name(self):
                return "bad"

        orch = _make_orchestrator(planner=BadPlanner())
        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "FAILED"
        assert "planner" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_handle_missing_tool(self):
        """Tool not in registry → run fails with resolution error."""
        planner = FakePlanner(responses=[
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="nonexistent_tool",
                reason="Try unknown tool",
            ),
        ])

        orch = _make_orchestrator(planner=planner)
        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "FAILED"
        assert "not registered" in result.error_message.lower() or "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_handle_tool_failure(self):
        """Tool fails → verification fails → run fails."""
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter(succeed=False))

        planner = FakePlanner(responses=[
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="browser",
                action_parameters={"action_type": "click"},
                reason="Click",
            ),
        ])

        orch = _make_orchestrator(planner=planner, registry=registry)
        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "FAILED"
        assert "verification failed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_handle_verifier_failure(self):
        """AlwaysFailVerifier → run fails even if tool succeeded."""
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter(succeed=True))

        planner = FakePlanner(responses=[
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="browser",
                action_parameters={"action_type": "click"},
                reason="Click",
            ),
        ])

        orch = _make_orchestrator(
            planner=planner,
            registry=registry,
            verifier=AlwaysFailVerifier(),
        )
        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "FAILED"

    @pytest.mark.asyncio
    async def test_stop_at_action_limit(self):
        """Run must stop when max_steps is reached."""
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter(succeed=True))

        # Planner always returns tool actions (never completes)
        infinite_actions = [
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="browser",
                action_parameters={"action_type": "click"},
                reason=f"Step {i}",
            )
            for i in range(20)
        ]

        planner = FakePlanner(responses=infinite_actions)
        orch = _make_orchestrator(
            planner=planner,
            registry=registry,
            max_steps=3,
        )
        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "FAILED"
        assert result.steps_completed <= 3

    @pytest.mark.asyncio
    async def test_wait_for_human_pauses_run(self):
        """Planner returns WAIT_FOR_HUMAN → run enters waiting state."""
        planner = FakePlanner(responses=[
            PlannerResponse(
                action_type=ActionType.WAIT_FOR_HUMAN,
                reason="Need human approval",
            ),
        ])

        orch = _make_orchestrator(planner=planner)
        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "WAITING_FOR_HUMAN"

    @pytest.mark.asyncio
    async def test_planner_declares_failure(self):
        """Planner returns FAIL → run enters FAILED state."""
        planner = FakePlanner(responses=[
            PlannerResponse(
                action_type=ActionType.FAIL,
                reason="Cannot complete task",
            ),
        ])

        orch = _make_orchestrator(planner=planner)
        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
        )
        assert result.final_status == "FAILED"
        assert "cannot complete" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_cancellation_respected(self):
        """Setting cancelled on context stops the loop."""
        registry = IntegrationRegistry()
        registry.register("browser", FakeToolAdapter(succeed=True))

        responses = [
            PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name="browser",
                action_parameters={"action_type": "click"},
                reason=f"Step {i}",
            )
            for i in range(10)
        ]
        planner = FakePlanner(responses=responses)

        orch = _make_orchestrator(
            planner=planner,
            registry=registry,
            max_steps=50,
        )

        # Cancel after first step via callback
        def on_step(ctx, record):
            if ctx.action_count >= 1:
                ctx.mark_cancelled()

        result = await orch.execute(
            task_id="t1", run_id="r1",
            task_type="test", task_configuration={},
            on_step_complete=on_step,
        )
        assert result.final_status == "CANCELLED"
        assert result.steps_completed == 1


# ═══════════════════════════════════════════════════════════════════
# EXECUTION CONTEXT TESTS
# ═══════════════════════════════════════════════════════════════════

class TestExecutionContext:
    """Test ExecutionContext limit checks."""

    def test_within_limits_initially(self):
        from datetime import timedelta
        ctx = ExecutionContext(
            task_id="t1", run_id="r1", task_type="test",
            max_steps=10, action_count=0,
            run_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert ctx.is_within_limits() is True

    def test_over_step_limit(self):
        from datetime import timedelta, datetime, timezone
        ctx = ExecutionContext(
            task_id="t1", run_id="r1", task_type="test",
            max_steps=5, action_count=5,
            run_deadline=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert ctx.is_within_limits() is False

    def test_past_deadline(self):
        from datetime import timedelta, datetime, timezone
        ctx = ExecutionContext(
            task_id="t1", run_id="r1", task_type="test",
            max_steps=100, action_count=0,
            run_deadline=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert ctx.is_within_limits() is False

    def test_mark_cancelled(self):
        ctx = ExecutionContext(
            task_id="t1", run_id="r1", task_type="test",
        )
        assert ctx.cancelled is False
        ctx.mark_cancelled()
        assert ctx.cancelled is True


# Need datetime imports for ExecutionContext tests
from datetime import datetime, timezone
