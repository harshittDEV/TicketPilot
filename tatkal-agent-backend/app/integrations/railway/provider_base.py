"""
Base Provider Interface for Railway Data Integrations.

Enforces provider capability declarations and uniform method signatures.
Each provider explicitly declares which capabilities it supports so callers
never guess or assume a feature is implemented.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from app.integrations.railway.contracts import (
    LiveRunningStatus,
    PnrStatus,
    ProviderCapabilities,
    Station,
    TrainBetweenStations,
    TrainSchedule,
)


class RailwayProviderBase(ABC):
    """Abstract base class for railway data providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. 'static_dataset', 'rapidapi')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return declared capabilities, rate limits, and configuration state."""
        pass

    @abstractmethod
    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        """Search railway stations by code or name."""
        pass

    @abstractmethod
    async def get_trains_between(
        self,
        source_code: str,
        dest_code: str,
        journey_date: str,
        travel_class: Optional[str] = None,
    ) -> list[TrainBetweenStations]:
        """Query genuine trains running between origin and destination."""
        pass

    @abstractmethod
    async def get_train_schedule(self, train_number: str) -> Optional[TrainSchedule]:
        """Retrieve detailed stop timetable for a specific train."""
        pass

    @abstractmethod
    async def get_live_running_status(
        self,
        train_number: str,
        journey_date: str,
    ) -> LiveRunningStatus:
        """Retrieve live running telemetry if supported, or truthful unavailable message."""
        pass

    @abstractmethod
    async def get_pnr_status(self, pnr_number: str) -> PnrStatus:
        """Check PNR booking status if supported, or truthful unsupported message."""
        pass
