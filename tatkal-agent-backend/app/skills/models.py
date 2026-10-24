"""
Skill system data models and schema validation.

Enforces strict structure on YAML/JSON workflow definitions, preventing
arbitrary code execution while supporting templated workflow execution.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class SkillInput(BaseModel):
    """Specification of an input variable required by a skill."""
    name: str = Field(..., description="Variable name used in parameter templates")
    type: str = Field("string", description="Expected type: string, integer, boolean, object")
    description: str = Field("", description="Human-readable description")
    default: Optional[Any] = Field(None, description="Default value if not provided")
    required: bool = Field(True, description="Whether this input is mandatory")


class SkillStep(BaseModel):
    """A single discrete step within a skill workflow."""
    step_id: str = Field(..., description="Unique step identifier within the skill")
    tool_name: str = Field(..., description="Tool adapter to invoke (e.g. 'browser', 'desktop')")
    action_type: str = Field(..., description="Action capability on the tool")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action arguments, supports {{ inputs.var }}")
    expected_outcome: Optional[str] = Field(None, description="Expected outcome string for verification")
    timeout_seconds: Optional[float] = Field(None, description="Step execution timeout in seconds")
    optional: bool = Field(False, description="If True, failure does not abort the skill")
    require_human: bool = Field(False, description="Pause for human approval or verification before/after")
    description: Optional[str] = Field(None, description="Human-readable description of what this step does")


class SkillDefinition(BaseModel):
    """
    Validated definition of a declarative agent skill.

    Skills allow orchestrating multi-step workflows without hardcoding
    automation scripts in the Python backend.
    """
    name: str = Field(..., description="Unique skill identifier (e.g. 'browser_inspection')")
    version: str = Field("1.0.0", description="Skill semantic version")
    description: str = Field("", description="Skill purpose and description")
    required_inputs: list[SkillInput] = Field(default_factory=list, description="Declared input parameters")
    allowed_tools: list[str] = Field(default_factory=list, description="Whitelist of tool names this skill may use")
    steps: list[SkillStep] = Field(default_factory=list, description="Ordered workflow steps")
    expected_outcomes: list[str] = Field(default_factory=list, description="Expected end-state criteria")
    timeout_seconds: float = Field(300.0, ge=1.0, description="Overall skill execution timeout")
    human_intervention_required: bool = Field(False, description="Whether human checkpoints are mandatory")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Skill name cannot be empty")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Skill name must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @field_validator("steps")
    @classmethod
    def validate_step_ids_unique(cls, steps: list[SkillStep]) -> list[SkillStep]:
        seen = set()
        for s in steps:
            if s.step_id in seen:
                raise ValueError(f"Duplicate step_id '{s.step_id}' found in skill definition")
            seen.add(s.step_id)
        return steps


class SkillStepResult(BaseModel):
    """Outcome of an individual executed skill step."""
    step_id: str
    tool_name: str
    action_type: str
    success: bool
    status: str
    requires_human: bool = False
    output: Any = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None


class SkillExecutionResult(BaseModel):
    """Comprehensive summary returned after running a skill."""
    skill_name: str
    success: bool
    status: str  # "completed", "failed", "waiting_for_human", "cancelled"
    steps_completed: int
    total_steps: int
    step_results: list[SkillStepResult] = Field(default_factory=list)
    error_message: Optional[str] = None
    requires_human: bool = False
    human_intervention_details: Optional[dict[str, Any]] = None
    output: dict[str, Any] = Field(default_factory=dict)
