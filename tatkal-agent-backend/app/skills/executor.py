"""
Skill execution engine.

Coordinates execution of declarative skill steps using the existing
ToolExecutor, IntegrationRegistry, Observer, and Verifier.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.agent.models import (
    ActionType,
    ExecutionContext,
    PlannerResponse,
    ToolResult,
)
from app.agent.observer import BaseObserver
from app.agent.tool_executor import ToolExecutor
from app.agent.verifier import BaseVerifier
from app.integrations.contracts import ToolActionStatus
from app.integrations.registry import IntegrationRegistry
from app.skills.loader import SkillLoader
from app.skills.models import (
    SkillDefinition,
    SkillExecutionResult,
    SkillStep,
    SkillStepResult,
)

logger = logging.getLogger(__name__)


class SkillExecutionError(Exception):
    """Base error during skill execution."""


class SkillExecutor:
    """
    Executes declarative skills step-by-step.

    Delegates individual action execution to the existing ``ToolExecutor``,
    preserving limits, error normalization, and lifecycle semantics.
    """

    def __init__(
        self,
        loader: SkillLoader,
        tool_executor: ToolExecutor,
        registry: IntegrationRegistry,
        observer: Optional[BaseObserver] = None,
        verifier: Optional[BaseVerifier] = None,
    ) -> None:
        self._loader = loader
        self._tool_executor = tool_executor
        self._registry = registry
        self._observer = observer
        self._verifier = verifier

    def _interpolate_value(self, value: Any, inputs: dict[str, Any], step_outputs: dict[str, Any]) -> Any:
        """Replace {{ inputs.var }} and {{ steps.step_id.key }} in parameter values."""
        if not isinstance(value, str):
            return value

        # Direct exact match replacement for non-string types
        m_exact = re.fullmatch(r"\{\{\s*inputs\.(\w+)\s*\}\}", value)
        if m_exact:
            var_name = m_exact.group(1)
            return inputs.get(var_name, value)

        # In-string substring replacement
        def repl(match: re.Match) -> str:
            path = match.group(1).split(".")
            if len(path) == 2 and path[0] == "inputs":
                return str(inputs.get(path[1], match.group(0)))
            if len(path) == 3 and path[0] == "steps":
                step_id, key = path[1], path[2]
                step_out = step_outputs.get(step_id, {})
                if isinstance(step_out, dict):
                    return str(step_out.get(key, match.group(0)))
            return match.group(0)

        return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, value)

    def _interpolate_params(
        self, params: dict[str, Any], inputs: dict[str, Any], step_outputs: dict[str, Any]
    ) -> dict[str, Any]:
        result = {}
        for k, v in params.items():
            if isinstance(v, dict):
                result[k] = self._interpolate_params(v, inputs, step_outputs)
            elif isinstance(v, list):
                result[k] = [self._interpolate_value(item, inputs, step_outputs) for item in v]
            else:
                result[k] = self._interpolate_value(v, inputs, step_outputs)
        return result

    def validate_inputs(self, skill: SkillDefinition, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Validate provided input values against the skill's declared required_inputs.

        Applies default values for optional inputs.

        Raises:
            ValueError: If a required input is missing.
        """
        resolved: dict[str, Any] = dict(inputs)
        for req in skill.required_inputs:
            if req.name not in resolved or resolved[req.name] is None:
                if req.required and req.default is None:
                    raise ValueError(f"Missing required input '{req.name}' for skill '{skill.name}'")
                if req.default is not None:
                    resolved[req.name] = req.default
        return resolved

    def verify_tools_available(self, skill: SkillDefinition) -> None:
        """
        Verify that all tools declared by the skill are registered and available.

        Raises:
            SkillExecutionError: If any tool is missing or unavailable.
        """
        for tool_name in skill.allowed_tools:
            is_reg = self._registry.is_registered(tool_name)
            if not is_reg and hasattr(self._registry, "is_tool_registered"):
                is_reg = self._registry.is_tool_registered(tool_name)

            if not is_reg:
                raise SkillExecutionError(
                    f"Skill '{skill.name}' requires tool '{tool_name}', but it is not registered"
                )

            tool = (
                self._registry.get_tool(tool_name)
                if hasattr(self._registry, "get_tool")
                else self._registry.get(tool_name)
            )
            if hasattr(tool, "is_available") and not tool.is_available:
                raise SkillExecutionError(
                    f"Skill '{skill.name}' requires tool '{tool_name}', but it is currently unavailable"
                )

    async def execute_skill(
        self,
        skill_name: str,
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> SkillExecutionResult:
        """
        Execute all workflow steps of a skill in declared order.

        Args:
            skill_name: The registered skill name.
            inputs: User or task configuration inputs.
            context: Current agent execution context.

        Returns:
            A structured SkillExecutionResult.
        """
        skill = self._loader.get_skill(skill_name)
        resolved_inputs = self.validate_inputs(skill, inputs)
        self.verify_tools_available(skill)

        step_results: list[SkillStepResult] = []
        step_outputs: dict[str, Any] = {}
        steps_completed = 0

        logger.info("Executing skill '%s' (%d steps)", skill_name, len(skill.steps))

        from app.services.audit_service import get_audit_service
        get_audit_service().record_event(
            event_type="skill.execution.started",
            event_category="SKILL",
            outcome="PENDING",
            source="skill_executor",
            task_id=context.task_id,
            run_id=context.run_id,
            tool_or_skill_name=skill_name,
            metadata={"inputs": resolved_inputs, "total_steps": len(skill.steps)},
        )

        for step in skill.steps:
            # Check cancellation and execution limits
            if context.cancelled:
                return SkillExecutionResult(
                    skill_name=skill_name,
                    success=False,
                    status="cancelled",
                    steps_completed=steps_completed,
                    total_steps=len(skill.steps),
                    step_results=step_results,
                    error_message="Execution cancelled",
                    output=step_outputs,
                )

            if not context.is_within_limits():
                return SkillExecutionResult(
                    skill_name=skill_name,
                    success=False,
                    status="failed",
                    steps_completed=steps_completed,
                    total_steps=len(skill.steps),
                    step_results=step_results,
                    error_message="Execution limit exceeded",
                    output=step_outputs,
                )

            # Check human checkpoint
            if step.require_human:
                logger.info("Step '%s' requires human intervention", step.step_id)
                return SkillExecutionResult(
                    skill_name=skill_name,
                    success=False,
                    status="waiting_for_human",
                    steps_completed=steps_completed,
                    total_steps=len(skill.steps),
                    step_results=step_results,
                    requires_human=True,
                    human_intervention_details={
                        "step_id": step.step_id,
                        "description": step.description or "Human confirmation required",
                    },
                    output=step_outputs,
                )

            # Interpolate parameters
            interpolated_params = self._interpolate_params(step.parameters, resolved_inputs, step_outputs)
            interpolated_params["action_type"] = step.action_type
            if step.timeout_seconds:
                interpolated_params["timeout_seconds"] = step.timeout_seconds

            # Construct structured plan action for ToolExecutor
            plan = PlannerResponse(
                action_type=ActionType.TOOL_ACTION,
                tool_name=step.tool_name,
                action_parameters=interpolated_params,
                expected_result=step.expected_outcome,
                reason=step.description or f"Executing skill step {step.step_id}",
            )

            # Execute tool action
            tool_result: ToolResult = await self._tool_executor.execute(plan, context)

            step_res = SkillStepResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                action_type=step.action_type,
                success=tool_result.success,
                status=tool_result.status.value,
                requires_human=tool_result.requires_human,
                output=tool_result.output,
                error_message=tool_result.error_message,
                duration_seconds=tool_result.duration_seconds,
            )
            step_results.append(step_res)

            # Check if human intervention was flagged by the tool
            if tool_result.requires_human or tool_result.status == ToolActionStatus.HUMAN_INTERVENTION_REQUIRED:
                return SkillExecutionResult(
                    skill_name=skill_name,
                    success=False,
                    status="waiting_for_human",
                    steps_completed=steps_completed,
                    total_steps=len(skill.steps),
                    step_results=step_results,
                    requires_human=True,
                    human_intervention_details={
                        "step_id": step.step_id,
                        "error": tool_result.error_message,
                        "output": tool_result.output,
                    },
                    output=step_outputs,
                )

            # Handle step failure
            if not tool_result.success:
                if not step.optional:
                    logger.warning("Required skill step '%s' failed: %s", step.step_id, tool_result.error_message)
                    from app.services.audit_service import get_audit_service
                    get_audit_service().record_skill_execution(
                        run_id=context.run_id,
                        task_id=context.task_id,
                        skill_name=skill_name,
                        outcome="FAILURE",
                        inputs=resolved_inputs,
                        error=f"Step '{step.step_id}' failed: {tool_result.error_message}",
                    )
                    return SkillExecutionResult(
                        skill_name=skill_name,
                        success=False,
                        status="failed",
                        steps_completed=steps_completed,
                        total_steps=len(skill.steps),
                        step_results=step_results,
                        error_message=f"Step '{step.step_id}' failed: {tool_result.error_message}",
                        output=step_outputs,
                    )

            # Record step outputs
            if tool_result.output and isinstance(tool_result.output, dict):
                step_outputs[step.step_id] = tool_result.output
            elif tool_result.output is not None:
                step_outputs[step.step_id] = {"result": tool_result.output}

            steps_completed += 1
            context.current_step += 1
            context.action_count += 1

        logger.info("Skill '%s' completed successfully (%d steps)", skill_name, steps_completed)
        from app.services.audit_service import get_audit_service
        get_audit_service().record_skill_execution(
            run_id=context.run_id,
            task_id=context.task_id,
            skill_name=skill_name,
            outcome="SUCCESS",
            inputs=resolved_inputs,
        )
        return SkillExecutionResult(
            skill_name=skill_name,
            success=True,
            status="completed",
            steps_completed=steps_completed,
            total_steps=len(skill.steps),
            step_results=step_results,
            output=step_outputs,
        )
