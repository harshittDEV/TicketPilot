"""
Unified Railway Data Service (Phase 9).

Orchestrates:
1. Local verified station directory lookup
2. Multi-provider train searches with automatic failover to official open static datasets
3. Granular cache management with freshness classification
4. Bounded timeouts, circuit breakers, and rate limit handling
5. Strict refusal to fabricate live telemetry, fares, or seat availability
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import get_settings
from app.integrations.railway.cache_manager import get_cache_manager
from app.integrations.railway.contracts import (
    DataFreshnessCategory,
    LiveRunningStatus,
    PnrStatus,
    ProviderStatusResponse,
    Station,
    TrainBetweenStations,
    TrainSchedule,
)
from app.integrations.railway.external_api_provider import ExternalApiRailwayProvider
from app.integrations.railway.provider_base import RailwayProviderBase
from app.integrations.railway.static_dataset_provider import StaticDatasetRailwayProvider
from app.integrations.railway.station_directory import (
    get_station_by_code,
    list_all_stations,
    normalize_station_input,
    search_stations,
)

logger = logging.getLogger(__name__)


class RailwayDataService:
    """Service layer managing railway providers, failover, and caching."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache = get_cache_manager()
        self._static_provider = StaticDatasetRailwayProvider()
        self._external_provider = ExternalApiRailwayProvider()

    def get_provider_status(self) -> ProviderStatusResponse:
        """Report operating mode, registered provider capabilities, and cache metrics."""
        providers = [
            self._static_provider.get_capabilities(),
            self._external_provider.get_capabilities(),
        ]
        stats = self._cache.get_stats()
        return ProviderStatusResponse(
            active_mode=self._settings.railway_provider,
            providers=providers,
            cache_entries_count=stats.get("active_entries", 0),
            cache_stats=stats,
        )

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        """Search stations using verified directory."""
        return search_stations(query, limit)

    def get_station_details(self, code: str) -> Optional[Station]:
        """Retrieve details for a station code."""
        return get_station_by_code(code)

    def list_all_stations(self) -> list[Station]:
        """List all verified stations."""
        return list_all_stations()

    async def get_trains_between(
        self,
        source: str,
        destination: str,
        journey_date: str,
        travel_class: Optional[str] = None,
    ) -> list[TrainBetweenStations]:
        """
        Search genuine trains running between origin and destination.

        Failover policy:
        1. Check memory cache.
        2. If external API provider is configured and mode allows, query external API.
        3. Fall back to verified official open dataset.
        4. If no trains found in either source, return empty list (NEVER invent fake trains).
        """
        norm_source = normalize_station_input(source)
        norm_dest = normalize_station_input(destination)
        cls_key = travel_class or "ALL"
        cache_key = f"trains_between:{norm_source}:{norm_dest}:{journey_date}:{cls_key}"

        cached = self._cache.get(cache_key)
        if cached:
            data, freshness = cached
            # Tag cached items with CACHED freshness
            return [
                t.model_copy(update={"freshness_category": freshness})
                for t in data
            ]

        results: list[TrainBetweenStations] = []

        # 1. Try external provider if hybrid/rapidapi and configured
        if self._settings.railway_provider in ("hybrid", "rapidapi") and self._external_provider.is_configured:
            try:
                external_results = await self._external_provider.get_trains_between(
                    norm_source, norm_dest, journey_date, travel_class
                )
                if external_results:
                    results = external_results
            except Exception as exc:
                logger.warning("External provider failed: %s, falling back to static dataset", exc)

        # 2. Fall back to static open dataset if no external results
        if not results:
            results = await self._static_provider.get_trains_between(
                norm_source, norm_dest, journey_date, travel_class
            )

        # 3. Cache results
        if results:
            self._cache.set(
                cache_key,
                results,
                ttl_seconds=self._settings.railway_cache_ttl_timetable_seconds,
                source=results[0].data_source,
            )

        return results

    async def get_train_schedule(self, train_number: str) -> Optional[TrainSchedule]:
        """
        Retrieve stop-by-stop schedule for a train.
        """
        clean_num = train_number.strip()
        cache_key = f"schedule:{clean_num}"

        cached = self._cache.get(cache_key)
        if cached:
            data, freshness = cached
            return data.model_copy(update={"freshness_category": freshness})

        schedule: Optional[TrainSchedule] = None

        # 1. Try external provider if configured
        if self._settings.railway_provider in ("hybrid", "rapidapi") and self._external_provider.is_configured:
            try:
                schedule = await self._external_provider.get_train_schedule(clean_num)
            except Exception as exc:
                logger.warning("External schedule query failed: %s", exc)

        # 2. Fall back to static dataset
        if not schedule:
            schedule = await self._static_provider.get_train_schedule(clean_num)

        if schedule:
            self._cache.set(
                cache_key,
                schedule,
                ttl_seconds=self._settings.railway_cache_ttl_timetable_seconds,
                source=schedule.data_source,
            )

        return schedule

    async def get_live_running_status(
        self,
        train_number: str,
        journey_date: str,
    ) -> LiveRunningStatus:
        """
        Retrieve live running telemetry. If external provider unconfigured or unavailable,
        returns truthful UNAVAILABLE response with compliance disclosure.
        """
        clean_num = train_number.strip()
        cache_key = f"live:{clean_num}:{journey_date}"

        cached = self._cache.get(cache_key)
        if cached:
            data, freshness = cached
            return data.model_copy(update={"freshness_category": freshness})

        status: LiveRunningStatus
        if self._settings.railway_provider in ("hybrid", "rapidapi") and self._external_provider.is_configured:
            status = await self._external_provider.get_live_running_status(clean_num, journey_date)
        else:
            status = await self._static_provider.get_live_running_status(clean_num, journey_date)

        if status.is_available:
            self._cache.set(
                cache_key,
                status,
                ttl_seconds=self._settings.railway_cache_ttl_live_seconds,
                source=status.data_source,
            )

        return status

    async def get_pnr_status(self, pnr_number: str) -> PnrStatus:
        """
        Check PNR status. Returns truthful response without fabricating booking confirmations.
        """
        clean_pnr = pnr_number.strip()
        cache_key = f"pnr:{clean_pnr}"

        cached = self._cache.get(cache_key)
        if cached:
            data, freshness = cached
            return data.model_copy(update={"freshness_category": freshness})

        pnr: PnrStatus
        if self._settings.railway_provider in ("hybrid", "rapidapi") and self._external_provider.is_configured:
            pnr = await self._external_provider.get_pnr_status(clean_pnr)
        else:
            pnr = await self._static_provider.get_pnr_status(clean_pnr)

        if pnr.is_supported:
            self._cache.set(
                cache_key,
                pnr,
                ttl_seconds=300,  # 5 minutes
                source=pnr.data_source,
            )

        return pnr


# Singleton accessor
_service_instance: Optional[RailwayDataService] = None


def get_railway_service() -> RailwayDataService:
    global _service_instance
    if _service_instance is None:
        _service_instance = RailwayDataService()
    return _service_instance
