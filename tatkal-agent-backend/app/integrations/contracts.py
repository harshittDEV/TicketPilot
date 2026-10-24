"""
Integration contracts for teammate modules.

These are typed interfaces (Python Protocols) that define the boundaries
between the core backend and the modules built by other team members.
Each protocol is minimal and adapter-friendly — external implementations
can be wrapped without rewriting the core backend.

IMPORTANT:
    Do NOT add implementation logic here.  These are contracts only.
    Actual implementations will be provided by teammates and registered
    via the IntegrationRegistry.
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# A.  SCHEDULER INTEGRATION  (Team Member 2)
# ═══════════════════════════════════════════════════════════════════

class ScheduleRequest(BaseModel):
    """Parameters for requesting a scheduled execution run."""
    task_id: str = Field(..., description="Unique task identifier")
    execute_at: datetime = Field(..., description="UTC time to execute the task")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduleResult(BaseModel):
    """Result returned after scheduling or cancelling a run."""
    schedule_id: str
    status: str  # "scheduled" | "cancelled" | "failed"
    message: str = ""


@runtime_checkable
class SchedulerIntegration(Protocol):
    """Contract for the scheduler module."""

    @abstractmethod
    async def schedule_run(self, request: ScheduleRequest) -> ScheduleResult:
        """Request a scheduled execution run."""
        ...

    @abstractmethod
    async def cancel_run(self, schedule_id: str) -> ScheduleResult:
        """Cancel a previously scheduled run."""
        ...


# ═══════════════════════════════════════════════════════════════════
# B.  BOOKING ASSISTANCE INTEGRATION  (Team Member 2)
# ═══════════════════════════════════════════════════════════════════

class BookingContext(BaseModel):
    """Validated task context passed to the booking-assistance component."""
    task_id: str
    passenger_count: int = Field(ge=1)
    journey_details: dict[str, Any] = Field(default_factory=dict)


class BookingResult(BaseModel):
    """Structured result returned by the booking-assistance component."""
    task_id: str
    success: bool
    booking_reference: Optional[str] = None
    message: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class BookingAssistanceIntegration(Protocol):
    """Contract for the booking-assistance module."""

    @abstractmethod
    async def execute_booking(self, context: BookingContext) -> BookingResult:
        """Invoke booking assistance with a validated task context."""
        ...


# ═══════════════════════════════════════════════════════════════════
# C.  TRAIN COMPARISON INTEGRATION  (Team Member 3)
# ═══════════════════════════════════════════════════════════════════

class TrainQuery(BaseModel):
    """Parameters for requesting eligible train options."""
    source_station: str
    destination_station: str
    travel_date: str  # ISO 8601 date string
    travel_class: Optional[str] = None
    quota: str = "TATKAL"


class TrainCandidate(BaseModel):
    """A single train option returned by the comparison module."""
    train_number: str
    train_name: str
    departure_time: str
    arrival_time: str
    available_classes: list[str] = Field(default_factory=list)
    availability_status: str = ""
    fare: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrainComparisonResult(BaseModel):
    """Structured collection of candidate trains."""
    query: TrainQuery
    candidates: list[TrainCandidate] = Field(default_factory=list)
    message: str = ""


@runtime_checkable
class TrainComparisonIntegration(Protocol):
    """Contract for the train comparison module."""

    @abstractmethod
    async def find_trains(self, query: TrainQuery) -> TrainComparisonResult:
        """Request eligible train options for the given query."""
        ...


# ═══════════════════════════════════════════════════════════════════
# D.  SECURITY INTEGRATION  (Team Member 3)
# ═══════════════════════════════════════════════════════════════════

class SecurityCheckRequest(BaseModel):
    """Parameters for a security validation or authorisation check."""
    action: str = Field(..., description="The sensitive action being requested")
    actor: str = Field(..., description="Identifier of the actor performing the action")
    resource: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)


class SecurityCheckResult(BaseModel):
    """Result of a security validation."""
    allowed: bool
    reason: str = ""


@runtime_checkable
class SecurityIntegration(Protocol):
    """Contract for the security module."""

    @abstractmethod
    async def check_authorization(
        self, request: SecurityCheckRequest
    ) -> SecurityCheckResult:
        """Check whether the requested action is authorised."""
        ...


# ═══════════════════════════════════════════════════════════════════
# E.  AGENT TOOL INTEGRATION  (Core — Phase 4)
# ═══════════════════════════════════════════════════════════════════

class ToolActionStatus(str, Enum):
    """Possible outcomes of a tool execution."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    INVALID_ARGUMENTS = "invalid_arguments"
    UNKNOWN_TOOL = "unknown_tool"
    TOOL_UNAVAILABLE = "tool_unavailable"
    RECOVERABLE_FAILURE = "recoverable_failure"
    NON_RECOVERABLE_FAILURE = "non_recoverable_failure"
    HUMAN_INTERVENTION_REQUIRED = "human_intervention_required"


class ToolAction(BaseModel):
    """A validated action to be executed by a tool adapter."""
    action_type: str = Field(..., description="e.g. 'click', 'type', 'screenshot', 'navigate'")
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 30.0


class ToolExecutionResult(BaseModel):
    """Structured result returned by a tool adapter."""
    status: ToolActionStatus
    output: Any = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolMetadata(BaseModel):
    """Metadata exposed by a tool adapter for safe discovery and dispatch."""
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field("", description="Human-readable tool description")
    version: str = Field("1.0.0", description="Tool version string")
    capabilities: list[str] = Field(
        default_factory=list, description="Action categories or capabilities"
    )
    input_schema: dict[str, Any] = Field(
        default_factory=dict, description="JSON schema or action parameter definitions"
    )
    is_available: bool = Field(
        True, description="Whether the tool is currently available for execution"
    )
    health_status: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic/health details"
    )


@runtime_checkable
class AgentToolIntegration(Protocol):
    """Minimal protocol for a tool adapter (browser, desktop, etc.)."""

    @abstractmethod
    async def execute(self, action: ToolAction) -> ToolExecutionResult:
        """Execute a validated action and return a structured result."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the tool adapter is operational."""
        ...

    def get_metadata(self) -> ToolMetadata:
        """Return metadata describing the tool's capabilities and schema."""
        ...

