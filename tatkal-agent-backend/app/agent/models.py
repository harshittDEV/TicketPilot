"""
Agent orchestration data models.

Pydantic schemas for structured communication between orchestrator
components: planner requests/responses, observations, verification
results, and execution context.

These schemas enforce validation on all LLM-produced plans before
execution.  Malformed plans are rejected — the orchestrator never
executes arbitrary code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════════════
# ACTION TYPES
# ═══════════════════════════════════════════════════════════════════

class ActionType(str, Enum):
    """Categories of actions the planner can propose."""
    TOOL_ACTION = "tool_action"          # Execute a registered tool
    OBSERVE = "observe"                  # Request an observation
    WAIT_FOR_HUMAN = "wait_for_human"    # Pause for human input
    COMPLETE = "complete"                # Declare task complete
    FAIL = "fail"                        # Declare unrecoverable failure


# ═══════════════════════════════════════════════════════════════════
# PLANNER REQUEST / RESPONSE
# ═══════════════════════════════════════════════════════════════════

class PlannerRequest(BaseModel):
    """Structured request sent to the planner (LLM or deterministic)."""
    task_type: str = Field(..., description="The task type identifier")
    task_configuration: dict[str, Any] = Field(
        default_factory=dict, description="Non-sensitive task config"
    )
    current_step: int = Field(0, ge=0, description="Current step number")
    max_steps: int = Field(100, ge=1, description="Maximum allowed steps")
    observation: Optional[dict[str, Any]] = Field(
        None, description="Current observation of the environment"
    )
    available_tools: list[str] = Field(
        default_factory=list, description="Names of registered tool adapters"
    )
    previous_actions: list[dict[str, Any]] = Field(
        default_factory=list, description="Summary of recent actions (not full history)"
    )
    system_instructions: Optional[str] = Field(
        None, description="System-level instructions for the planner"
    )


class PlannerResponse(BaseModel):
    """
    Structured response from the planner.

    Every field is validated before the orchestrator acts on it.
    The planner must return one of the defined ActionTypes.
    """
    action_type: ActionType = Field(..., description="What kind of action to take")
    tool_name: Optional[str] = Field(
        None, description="Tool to invoke (required for TOOL_ACTION)"
    )
    action_parameters: dict[str, Any] = Field(
        default_factory=dict, description="Validated parameters for the action"
    )
    reason: str = Field(
        "", max_length=1000, description="Why this action was chosen"
    )
    expected_result: Optional[str] = Field(
        None, max_length=500, description="What the planner expects to happen"
    )
    needs_observation: bool = Field(
        True, description="Whether a fresh observation is needed after execution"
    )
    task_complete: bool = Field(
        False, description="Whether the planner believes the task is done"
    )

    @field_validator("tool_name")
    @classmethod
    def tool_required_for_tool_action(cls, v: Optional[str], info) -> Optional[str]:
        # Validation handled at orchestrator level for cross-field checks
        return v


from app.integrations.contracts import ToolActionStatus


# ═══════════════════════════════════════════════════════════════════
# OBSERVATION
# ═══════════════════════════════════════════════════════════════════

class Observation(BaseModel):
    """
    Structured representation of the environment state.

    Supports browser URLs, page titles, bounded text excerpts, and
    screenshot artifact references.
    """
    observation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique observation identifier",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the observation was captured (UTC)",
    )
    source: str = Field(
        "system", description="What produced this observation"
    )
    content: dict[str, Any] = Field(
        default_factory=dict, description="Structured observation data"
    )
    url: Optional[str] = Field(
        None, description="Current browser URL if applicable"
    )
    title: Optional[str] = Field(
        None, description="Current page title if applicable"
    )
    text_excerpt: Optional[str] = Field(
        None, description="Bounded text excerpt from page or screen"
    )
    artifact_ref: Optional[str] = Field(
        None, description="Reference to an artifact (screenshot path, etc.)"
    )
    error: Optional[dict[str, Any]] = Field(
        None, description="Structured error if observation failed"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


# ═══════════════════════════════════════════════════════════════════
# VERIFICATION
# ═══════════════════════════════════════════════════════════════════

class VerificationResult(BaseModel):
    """
    Result of verifying whether an action succeeded.

    The orchestrator must not treat an unverified or failed
    verification as a success.
    """
    success: bool = Field(..., description="Whether the action succeeded")
    confidence: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Confidence/strength of the verification (0.0–1.0)",
    )
    explanation: str = Field(
        "", max_length=1000, description="Concise explanation"
    )
    mismatch: Optional[str] = Field(
        None, max_length=1000,
        description="Description of any detected mismatch",
    )


# ═══════════════════════════════════════════════════════════════════
# TOOL EXECUTION RESULT (extended view for orchestrator)
# ═══════════════════════════════════════════════════════════════════

class ToolResult(BaseModel):
    """
    Normalised tool execution result used within the orchestrator.

    Wraps the integration contract's ToolExecutionResult with
    additional orchestration metadata.
    """
    tool_name: str
    action_type: str
    success: bool
    status: ToolActionStatus = Field(default=ToolActionStatus.SUCCESS)
    requires_human: bool = Field(default=False)
    recoverable: bool = Field(default=False)
    output: Any = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    artifact_ref: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# EXECUTION CONTEXT
# ═══════════════════════════════════════════════════════════════════

class ExecutionContext(BaseModel):
    """
    In-memory execution context carried during a run.

    This is NOT the authoritative persistent state — the database
    remains the source of truth.  The context is a snapshot used
    to coordinate the current planning step.
    """
    task_id: str
    run_id: str
    task_type: str
    task_configuration: dict[str, Any] = Field(default_factory=dict)
    run_status: str = "PENDING"
    current_step: int = 0
    action_count: int = 0
    max_steps: int = 100
    max_run_duration_seconds: float = 3600.0
    max_action_timeout_seconds: float = 30.0
    run_deadline: Optional[datetime] = None
    cancelled: bool = False

    def is_within_limits(self) -> bool:
        """Check whether the run is still within configured limits."""
        if self.action_count >= self.max_steps:
            return False
        if self.run_deadline and datetime.now(timezone.utc) >= self.run_deadline:
            return False
        return True

    def mark_cancelled(self) -> None:
        """Set the cancellation flag."""
        self.cancelled = True


# ═══════════════════════════════════════════════════════════════════
# STEP LOG (for recording what happened at each step)
# ═══════════════════════════════════════════════════════════════════

class StepRecord(BaseModel):
    """Record of a single orchestrator step — for logging/debugging."""
    step_number: int
    action_type: str
    tool_name: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    tool_result: Optional[ToolResult] = None
    observation_before: Optional[str] = None  # observation_id
    observation_after: Optional[str] = None   # observation_id
    verification: Optional[VerificationResult] = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    duration_seconds: Optional[float] = None
