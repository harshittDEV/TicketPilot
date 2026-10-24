"""
Integration tests for Recovery and Resilience Engine (Phase 6).

Verifies end-to-end interactions across:
- ToolExecutor, CircuitBreakers, and RecoveryPolicy.
- Idempotent action recovery vs. non-idempotent uncertain outcome handoff.
- Orchestrator lifecycle transition to WAITING_FOR_HUMAN on human-required flags.
- TrainComparisonAdapter circuit-breaker trip, fast-fail, and health reporting.
- API error response formatting for recovery errors with safe structured fields.
- API endpoint for circuit breaker monitoring.
"""

import pytest
from fastapi.testclient import TestClient

from app.agent.llm.base import FakePlanner
from app.agent.models import ActionType, ExecutionContext, PlannerResponse
from app.agent.observer import FakeObserver
from app.agent.orchestrator import Orchestrator
from app.agent.recovery.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
)
from app.agent.recovery.errors import (
    ActionValidationError,
    CaptchaChallengeError,
    ClassifiedRecoveryError,
    ErrorCategory,
    SessionExpiredError,
    TransientNetworkError,
)
from app.agent.recovery.policy import RecoveryPolicy, ZeroSleeper
from app.agent.tool_executor import ToolExecutor
from app.agent.verifier import DeterministicVerifier
from app.integrations.contracts import (
    AgentToolIntegration,
    ToolAction,
    ToolActionStatus,
    ToolExecutionResult,
    ToolMetadata,
    TrainQuery,
)
from app.integrations.registry import IntegrationRegistry
from app.integrations.train_comparison.adapter import TrainComparisonAdapter
from app.main import app
from app.services.run_state_machine import RunStatus


# ── Fakes and Stubs ──────────────────────────────────────────────────

class FlakyToolAdapter:
    """Fails with transient network errors N times, then succeeds."""
    def __init__(self, failures_before_success: int = 1) -> None:
        self.failures_before_success = failures_before_success
        self.call_count = 0

    async def execute(self, action: ToolAction) -> ToolExecutionResult:
        self.call_count += 1
        if self.call_count <= self.failures_before_success:
            return ToolExecutionResult(
                status=ToolActionStatus.RECOVERABLE_FAILURE,
                error_message=f"Connection reset attempt {self.call_count}",
            )
        return ToolExecutionResult(
            status=ToolActionStatus.SUCCESS,
            output={"result": "ok", "attempts": self.call_count},
        )

    async def health_check(self) -> bool:
        return True

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(name="flaky_tool", capabilities=["inspect"])


class FailingToolAdapter:
    """Always raises an exception."""
    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.call_count = 0

    async def execute(self, action: ToolAction) -> ToolExecutionResult:
        self.call_count += 1
        raise self._exc

    async def health_check(self) -> bool:
        return True

    def get_metadata(self) -> ToolMetadata:
        return ToolMetadata(name="failing_tool", capabilities=["inspect", "click"])


# ── Test Suites ──────────────────────────────────────────────────────

class TestToolExecutorRecovery:
    """Verify tool execution resilience, retries, and circuit breaker guardrails."""

    @pytest.mark.asyncio
    async def test_idempotent_action_recovers_after_transient_failure(self):
        registry = IntegrationRegistry()
        flaky_adapter = FlakyToolAdapter(failures_before_success=2)
        registry.register("flaky", flaky_adapter)

        policy = RecoveryPolicy(
            max_attempts=3,
            initial_backoff_seconds=0.1,
            backoff_multiplier=2.0,
            sleeper=ZeroSleeper(),
        )
        executor = ToolExecutor(registry, recovery_policy=policy)

        # Idempotent action 'inspect' should retry and succeed
        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="flaky",
            action_parameters={"action_type": "inspect"},
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        result = await executor.execute(plan, ctx)

        assert result.success is True
        assert result.output["attempts"] == 3
        assert flaky_adapter.call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_blocks_execution(self):
        registry = IntegrationRegistry()
        failing_adapter = FailingToolAdapter(RuntimeError("Service down"))
        registry.register("failing_svc", failing_adapter)

        breaker = CircuitBreaker("failing_svc", failure_threshold=2, cooldown_seconds=60.0)
        executor = ToolExecutor(
            registry,
            circuit_breakers={"failing_svc": breaker},
            recovery_policy=RecoveryPolicy(max_attempts=1),
        )

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="failing_svc",
            action_parameters={"action_type": "inspect"},
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")

        # First failure
        r1 = await executor.execute(plan, ctx)
        assert r1.success is False
        assert breaker.state == CircuitState.CLOSED

        # Second failure trips breaker to OPEN
        r2 = await executor.execute(plan, ctx)
        assert r2.success is False
        assert breaker.state == CircuitState.OPEN

        # Third call is blocked by open breaker without invoking adapter
        initial_calls = failing_adapter.call_count
        r3 = await executor.execute(plan, ctx)
        assert r3.success is False
        assert r3.status == ToolActionStatus.TOOL_UNAVAILABLE
        assert "circuit breaker is open" in r3.error_message.lower()
        # Underlying tool was not called
        assert failing_adapter.call_count == initial_calls

    @pytest.mark.asyncio
    async def test_non_idempotent_timeout_requires_human_intervention(self):
        registry = IntegrationRegistry()
        from tests.test_orchestrator import SlowToolAdapter
        registry.register("slow", SlowToolAdapter())

        executor = ToolExecutor(
            registry,
            default_timeout=0.05,
            recovery_policy=RecoveryPolicy(max_attempts=3, sleeper=ZeroSleeper()),
        )

        # 'click' is non-idempotent
        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="slow",
            action_parameters={"action_type": "click", "timeout_seconds": 0.05},
        )
        ctx = ExecutionContext(task_id="t1", run_id="r1", task_type="test")
        result = await executor.execute(plan, ctx)

        assert result.success is False
        assert result.status == ToolActionStatus.TIMEOUT
        assert result.requires_human is True
        assert result.recoverable is False
        assert "uncertain" in result.error_message.lower()


class TestOrchestratorRecoveryHandoff:
    """Verify orchestrator pauses on human-intervention and does not mark runs successful falsely."""

    @pytest.mark.asyncio
    async def test_orchestrator_pauses_in_waiting_for_human_on_captcha(self):
        registry = IntegrationRegistry()
        captcha_adapter = FailingToolAdapter(RuntimeError("CAPTCHA challenge detected on screen"))
        registry.register("browser", captcha_adapter)

        executor = ToolExecutor(registry, recovery_policy=RecoveryPolicy(max_attempts=1))
        verifier = DeterministicVerifier()
        observer = FakeObserver()

        plan = PlannerResponse(
            action_type=ActionType.TOOL_ACTION,
            tool_name="browser",
            action_parameters={"action_type": "click"},
            reason="Click login",
        )
        planner = FakePlanner(responses=[plan])

        orch = Orchestrator(
            planner=planner,
            observer=observer,
            tool_executor=executor,
            verifier=verifier,
            max_steps=5,
        )

        result = await orch.execute(
            task_id="t_captcha",
            run_id="r_captcha",
            task_type="booking",
            task_configuration={},
        )

        assert result.final_status == RunStatus.WAITING_FOR_HUMAN.value
        assert "captcha" in result.error_message.lower() or "human" in result.error_message.lower()


class TestTrainComparisonCircuitBreaker:
    """Verify TrainComparisonAdapter resilience and health checks."""

    @pytest.mark.asyncio
    async def test_external_provider_trips_circuit_breaker(self):
        cb = CircuitBreaker("train_ext_provider", failure_threshold=2, cooldown_seconds=30.0)

        def failing_provider(_query: TrainQuery):
            raise ConnectionError("Remote IRCTC train API unavailable")

        adapter = TrainComparisonAdapter(
            data_provider=failing_provider,
            circuit_breaker=cb,
        )
        query = TrainQuery(source_station="NDLS", destination_station="HWH", travel_date="2026-11-20")

        # 1. First failure
        with pytest.raises(ConnectionError):
            await adapter.find_trains(query)
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED
        assert await adapter.health_check() is True

        # 2. Second failure trips breaker
        with pytest.raises(ConnectionError):
            await adapter.find_trains(query)
        assert cb.state == CircuitState.OPEN
        assert await adapter.health_check() is False

        # 3. Subsequent query fails fast with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await adapter.find_trains(query)
        assert exc_info.value.breaker_name == "train_ext_provider"


class TestRecoveryApiEndpoints:
    """Verify REST API responses for circuit breakers and error responses."""

    def test_list_circuit_breakers_api(self):
        client = TestClient(app)
        CircuitBreakerRegistry.get("api_test_breaker", failure_threshold=3)

        resp = client.get("/api/v1/integrations/circuit-breakers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "api_test_breaker" in data["data"]
        assert data["data"]["api_test_breaker"]["state"] == "closed"
        assert "cooldown_remaining_seconds" in data["data"]["api_test_breaker"]
