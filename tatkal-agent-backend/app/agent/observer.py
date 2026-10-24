"""
Observation interface.

Defines how the orchestrator obtains a structured representation of
the current environment.  Actual screenshot/DOM capture belongs to
Phase 4.  This phase provides the interface and a deterministic fake.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.agent.models import ExecutionContext, Observation


class BaseObserver(ABC):
    """
    Abstract base class for environment observers.

    Implementers capture the current state of the environment
    (browser, desktop, etc.) and return a structured Observation.
    """

    @abstractmethod
    async def observe(self, context: ExecutionContext) -> Observation:
        """
        Capture and return a structured observation of the environment.

        Args:
            context: Current execution context (task/run info).

        Returns:
            An Observation instance with captured data.
        """
        ...


class FakeObserver(BaseObserver):
    """
    Deterministic observer for testing.

    Returns pre-configured observations or a default empty observation.
    Never captures real screenshots or DOM data.
    """

    def __init__(
        self,
        observations: list[Observation] | None = None,
    ) -> None:
        self._observations = list(observations) if observations else []
        self._call_count = 0

    async def observe(self, context: ExecutionContext) -> Observation:
        self._call_count += 1

        if self._observations:
            return self._observations.pop(0)

        return Observation(
            source="fake_observer",
            content={
                "step": context.current_step,
                "status": "observed",
                "message": "Fake observation — no real environment capture",
            },
        )

    @property
    def call_count(self) -> int:
        return self._call_count


class DefaultObserver(BaseObserver):
    """
    Standard environment observer for Phase 4.

    Inspects registered tool adapters (browser, desktop) to assemble a
    normalized environment observation. Enforces text-size boundaries and
    records screenshot artifact references.
    """

    def __init__(
        self,
        registry: Any,
        *,
        capture_screenshots: bool = False,
        max_text_chars: int = 5000,
    ) -> None:
        self._registry = registry
        self._capture_screenshots = capture_screenshots
        self._max_text_chars = max_text_chars

    async def observe(self, context: ExecutionContext) -> Observation:
        url: str | None = None
        title: str | None = None
        text_excerpt: str | None = None
        artifact_ref: str | None = None
        error_info: dict | None = None
        source = "system"
        content: dict[str, Any] = {"step": context.current_step}

        # Check if browser adapter is registered
        if self._registry.is_registered("browser") or (
            hasattr(self._registry, "is_tool_registered")
            and self._registry.is_tool_registered("browser")
        ):
            try:
                from app.integrations.contracts import ToolAction
                browser = (
                    self._registry.get_tool("browser")
                    if hasattr(self._registry, "get_tool")
                    else self._registry.get("browser")
                )
                source = "browser"

                # Extract page state
                page_info = await browser.execute(ToolAction(action_type="inspect"))
                if page_info.output and isinstance(page_info.output, dict):
                    url = page_info.output.get("url")
                    title = page_info.output.get("title")
                    text_excerpt = page_info.output.get("text_excerpt")
                    content["browser_state"] = page_info.output

                # Capture screenshot if requested
                if self._capture_screenshots:
                    shot_res = await browser.execute(
                        ToolAction(
                            action_type="screenshot",
                            parameters={"run_id": context.run_id},
                        )
                    )
                    if shot_res.output and isinstance(shot_res.output, dict):
                        artifact_ref = shot_res.output.get("artifact_ref")

            except Exception as exc:
                error_info = {"code": "OBSERVATION_ERROR", "message": str(exc)}
                content["observation_error"] = str(exc)

        # Bound text excerpt length
        if text_excerpt and len(text_excerpt) > self._max_text_chars:
            text_excerpt = text_excerpt[: self._max_text_chars]

        return Observation(
            source=source,
            url=url,
            title=title,
            text_excerpt=text_excerpt,
            artifact_ref=artifact_ref,
            error=error_info,
            content=content,
            metadata={"run_id": context.run_id, "step": context.current_step},
        )

