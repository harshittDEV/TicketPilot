"""
Provider-agnostic LLM client interface.

The rest of the application depends only on this abstract interface.
Concrete provider adapters (OpenAI, Anthropic, Gemini, etc.) can be
implemented behind it.  A deterministic ``FakePlanner`` is provided
for testing.

No provider SDK is imported here.
No API key is required for the application to start.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agent.models import PlannerRequest, PlannerResponse


# ═══════════════════════════════════════════════════════════════════
# LLM REQUEST / RESPONSE WRAPPERS
# ═══════════════════════════════════════════════════════════════════

class LLMRequest(BaseModel):
    """Provider-neutral request to the LLM."""
    planner_request: PlannerRequest
    model_name: Optional[str] = None
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1)
    timeout_seconds: float = Field(30.0, gt=0)


class LLMResponse(BaseModel):
    """Provider-neutral response from the LLM."""
    planner_response: PlannerResponse
    raw_text: Optional[str] = None
    model_name: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    provider: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMError(BaseModel):
    """Normalised LLM provider error."""
    provider: str
    error_type: str  # "timeout" | "rate_limit" | "auth" | "parse" | "unknown"
    message: str
    retryable: bool = False


# ═══════════════════════════════════════════════════════════════════
# ABSTRACT LLM CLIENT
# ═══════════════════════════════════════════════════════════════════

class BaseLLMClient(ABC):
    """
    Abstract base class for LLM provider clients.

    Implementers must:
        - Accept an LLMRequest.
        - Return an LLMResponse with a validated PlannerResponse.
        - Normalise provider-specific errors into LLMError.
        - Never log prompts containing sensitive information.
    """

    @abstractmethod
    async def plan(self, request: LLMRequest) -> LLMResponse:
        """
        Send a planning request and return a structured response.

        Raises:
            PlannerError: If the response cannot be parsed.
            PlannerTimeoutError: If the provider does not respond in time.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the LLM provider is reachable."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        ...


# ═══════════════════════════════════════════════════════════════════
# FAKE PLANNER (for tests — no API key required)
# ═══════════════════════════════════════════════════════════════════

class FakePlanner(BaseLLMClient):
    """
    Deterministic planner for testing.

    Returns pre-configured responses or a default "complete" action.
    Never contacts an external service.
    """

    def __init__(
        self,
        responses: list[PlannerResponse] | None = None,
        fail_after: int | None = None,
        fail_with: Exception | None = None,
    ) -> None:
        """
        Args:
            responses: Ordered list of responses to return. When exhausted,
                       returns a COMPLETE action.
            fail_after: After this many calls, raise ``fail_with``.
            fail_with: Exception to raise after ``fail_after`` calls.
        """
        self._responses = list(responses) if responses else []
        self._call_count = 0
        self._fail_after = fail_after
        self._fail_with = fail_with

    async def plan(self, request: LLMRequest) -> LLMResponse:
        self._call_count += 1

        # Simulate failure after N calls
        if (
            self._fail_after is not None
            and self._call_count > self._fail_after
            and self._fail_with is not None
        ):
            raise self._fail_with

        # Return pre-configured response or default completion
        if self._responses:
            response = self._responses.pop(0)
        else:
            from app.agent.models import ActionType
            response = PlannerResponse(
                action_type=ActionType.COMPLETE,
                reason="No more planned actions",
                task_complete=True,
            )

        return LLMResponse(
            planner_response=response,
            raw_text=None,
            provider="fake",
            model_name="fake-planner",
        )

    async def health_check(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def call_count(self) -> int:
        return self._call_count
