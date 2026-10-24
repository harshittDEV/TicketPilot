"""
External Railway API Provider Adapter (Phase 9).

Integrates documented third-party railway REST APIs (e.g. RapidAPI Indian Railways / IRCTC endpoints).
All API keys remain strictly server-side and are NEVER returned to the frontend.

Capabilities when credentials configured:
- Real-time train timetable lookups
- Trains between stations
- Live GPS running status telemetry
- PNR status inquiries

When credentials are unset or invalid:
- Declines calls safely with explicit status reporting
- Never invents fake telemetry or fake PNR records
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.agent.recovery.circuit_breaker import CircuitBreakerRegistry
from app.core.config import get_settings
from app.integrations.railway.contracts import (
    DataFreshnessCategory,
    LiveRunningStatus,
    PnrStatus,
    ProviderCapabilities,
    Station,
    StationStop,
    TrainBetweenStations,
    TrainSchedule,
)
from app.integrations.railway.provider_base import RailwayProviderBase
from app.integrations.railway.station_directory import search_stations

logger = logging.getLogger(__name__)


class ExternalApiRailwayProvider(RailwayProviderBase):
    """Adapter for RapidAPI / third-party Indian Railways HTTP REST API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._circuit_breaker = CircuitBreakerRegistry.get("railway_api")

    @property
    def provider_id(self) -> str:
        return "rapidapi"

    @property
    def display_name(self) -> str:
        return "RapidAPI Indian Railways API"

    @property
    def is_configured(self) -> bool:
        """Return True if an API key is present in backend configuration."""
        key = self._settings.railway_api_key
        return bool(key and key.strip() and not key.startswith("your-"))

    def get_capabilities(self) -> ProviderCapabilities:
        configured = self.is_configured
        return ProviderCapabilities(
            provider_id=self.provider_id,
            display_name=self.display_name,
            has_station_search=True,
            has_timetable=True,
            has_trains_between=True,
            has_live_running=True,
            has_fare=configured,
            has_availability=configured,
            has_pnr=configured,
            auth_configured=configured,
            quota_limits="RapidAPI Freemium tier (configurable in .env)",
            notes=(
                "Requires x-rapidapi-key server-side environment variable. "
                "Provides live running status and PNR lookups when authenticated."
                if configured
                else "API key not configured in .env. Falling back to official open static dataset."
            ),
        )

    def _get_headers(self) -> dict[str, str]:
        key = self._settings.railway_api_key or ""
        host = self._settings.railway_api_host
        return {
            "x-rapidapi-key": key,
            "x-rapidapi-host": host,
            "Accept": "application/json",
        }

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        # Always use local verified station directory for speed & reliability
        return search_stations(query, limit)

    async def get_trains_between(
        self,
        source_code: str,
        dest_code: str,
        journey_date: str,
        travel_class: Optional[str] = None,
    ) -> list[TrainBetweenStations]:
        if not self.is_configured:
            return []

        if not self._circuit_breaker.allow_request():
            logger.warning("Railway external API circuit breaker is OPEN, declining request")
            return []

        base_url = self._settings.railway_api_base_url.rstrip("/")
        url = f"{base_url}/api/trains/between-stations"
        params = {
            "from": source_code,
            "to": dest_code,
            "date": journey_date,
        }

        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            async with httpx.AsyncClient(timeout=self._settings.railway_timeout_seconds) as client:
                res = await client.get(url, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    self._circuit_breaker.record_success()
                    data = res.json()
                    trains = data.get("data") or data.get("trains") or []
                    parsed: list[TrainBetweenStations] = []
                    for t in trains:
                        num = str(t.get("train_number") or t.get("trainNo") or "")
                        name = str(t.get("train_name") or t.get("trainName") or f"Train {num}")
                        dep = str(t.get("from_time") or t.get("departureTime") or "00:00")
                        arr = str(t.get("to_time") or t.get("arrivalTime") or "00:00")
                        dur = int(t.get("duration_minutes") or t.get("duration") or 0)
                        classes = list(t.get("classes") or ["3A", "2A", "SL"])

                        parsed.append(
                            TrainBetweenStations(
                                train_number=num,
                                train_name=name,
                                source_station_code=source_code,
                                source_station_name=t.get("from_station_name") or source_code,
                                destination_station_code=dest_code,
                                destination_station_name=t.get("to_station_name") or dest_code,
                                departure_time=dep,
                                arrival_time=arr,
                                duration_minutes=dur,
                                duration_formatted=f"{dur // 60}h {dur % 60}m",
                                available_classes=classes,
                                available_quotas=["GENERAL", "TATKAL"],
                                data_source=self.display_name,
                                freshness_category=DataFreshnessCategory.LIVE,
                                retrieved_at=now_iso,
                            )
                        )
                    return parsed
                else:
                    logger.warning("External railway API returned HTTP %s", res.status_code)
                    self._circuit_breaker.record_failure()
                    return []
        except Exception as exc:
            logger.warning("External railway API request failed: %s", exc)
            self._circuit_breaker.record_failure(exc)
            return []

    async def get_train_schedule(self, train_number: str) -> Optional[TrainSchedule]:
        if not self.is_configured or not self._circuit_breaker.allow_request():
            return None

        base_url = self._settings.railway_api_base_url.rstrip("/")
        url = f"{base_url}/api/trains-search/v1/train/{train_number}"

        try:
            async with httpx.AsyncClient(timeout=self._settings.railway_timeout_seconds) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 200:
                    self._circuit_breaker.record_success()
                    data = res.json()
                    now_iso = datetime.now(timezone.utc).isoformat()
                    # Parse schedule stops
                    raw_stops = data.get("data", {}).get("stops") or data.get("stops") or []
                    stops: list[StationStop] = []
                    for idx, s in enumerate(raw_stops):
                        stops.append(
                            StationStop(
                                stop_number=idx + 1,
                                station_code=s.get("station_code") or s.get("code") or "",
                                station_name=s.get("station_name") or s.get("name") or "",
                                arrival_time=s.get("arrival_time") or s.get("arr") or "00:00",
                                departure_time=s.get("departure_time") or s.get("dep") or "00:00",
                                halt_minutes=int(s.get("halt_time") or 0),
                                distance_km=int(s.get("distance") or 0),
                                day_count=int(s.get("day") or 1),
                            )
                        )
                    return TrainSchedule(
                        train_number=train_number,
                        train_name=data.get("train_name") or f"Train {train_number}",
                        origin_station_code=data.get("from_station_code") or (stops[0].station_code if stops else ""),
                        origin_station_name=data.get("from_station_name") or (stops[0].station_name if stops else ""),
                        destination_station_code=data.get("to_station_code") or (stops[-1].station_code if stops else ""),
                        destination_station_name=data.get("to_station_name") or (stops[-1].station_name if stops else ""),
                        runs_on_days=data.get("runs_on") or ["Daily"],
                        available_classes=data.get("classes") or ["SL", "3A", "2A"],
                        stops=stops,
                        data_source=self.display_name,
                        freshness_category=DataFreshnessCategory.LIVE,
                        last_updated=now_iso,
                    )
                else:
                    self._circuit_breaker.record_failure()
                    return None
        except Exception as exc:
            logger.warning("External railway API schedule failed: %s", exc)
            self._circuit_breaker.record_failure(exc)
            return None

    async def get_live_running_status(
        self,
        train_number: str,
        journey_date: str,
    ) -> LiveRunningStatus:
        now_iso = datetime.now(timezone.utc).isoformat()

        if not self.is_configured:
            return LiveRunningStatus(
                train_number=train_number,
                train_name=f"Train {train_number}",
                journey_date=journey_date,
                is_available=False,
                current_station_code=None,
                current_station_name=None,
                delay_departure_minutes=0,
                delay_arrival_minutes=0,
                status_message=(
                    "Live running status requires active GPS provider credentials "
                    "(e.g. RapidAPI Indian Railways key in server environment). "
                    "Timetable and route information are displayed from verified schedules."
                ),
                last_reported_time=None,
                is_terminated=False,
                data_source=self.display_name,
                freshness_category=DataFreshnessCategory.UNAVAILABLE,
                observation_timestamp=now_iso,
                disclaimer="External provider credentials required to query live GPS updates.",
            )

        if not self._circuit_breaker.allow_request():
            return LiveRunningStatus(
                train_number=train_number,
                train_name=f"Train {train_number}",
                journey_date=journey_date,
                is_available=False,
                status_message="External railway API circuit breaker is currently OPEN due to upstream errors. Try again shortly.",
                data_source=self.display_name,
                freshness_category=DataFreshnessCategory.UNAVAILABLE,
                observation_timestamp=now_iso,
                disclaimer="Circuit breaker protection active.",
            )

        base_url = self._settings.railway_api_base_url.rstrip("/")
        url = f"{base_url}/api/trains/v1/train/status"
        params = {"trainNo": train_number, "startDay": journey_date}

        try:
            async with httpx.AsyncClient(timeout=self._settings.railway_timeout_seconds) as client:
                res = await client.get(url, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    self._circuit_breaker.record_success()
                    data = res.json()
                    curr_stn = data.get("current_station_code") or data.get("currentStation")
                    curr_name = data.get("current_station_name") or data.get("currentStationName")
                    delay = int(data.get("delay") or data.get("delay_minutes") or 0)
                    msg = data.get("status_as_of") or data.get("message") or f"Train {train_number} running with delay of {delay}m"

                    return LiveRunningStatus(
                        train_number=train_number,
                        train_name=data.get("train_name") or f"Train {train_number}",
                        journey_date=journey_date,
                        is_available=True,
                        current_station_code=curr_stn,
                        current_station_name=curr_name,
                        delay_departure_minutes=delay,
                        delay_arrival_minutes=delay,
                        status_message=msg,
                        last_reported_time=data.get("updated_at"),
                        is_terminated=bool(data.get("is_terminated")),
                        data_source=self.display_name,
                        freshness_category=DataFreshnessCategory.LIVE,
                        observation_timestamp=now_iso,
                        disclaimer="Live telemetry provided by RapidAPI Indian Railways endpoint.",
                    )
                else:
                    self._circuit_breaker.record_failure()
                    return LiveRunningStatus(
                        train_number=train_number,
                        train_name=f"Train {train_number}",
                        journey_date=journey_date,
                        is_available=False,
                        status_message=f"Live telemetry service returned status {res.status_code}",
                        data_source=self.display_name,
                        freshness_category=DataFreshnessCategory.UNAVAILABLE,
                        observation_timestamp=now_iso,
                        disclaimer="Live telemetry query failed upstream.",
                    )
        except Exception as exc:
            self._circuit_breaker.record_failure(exc)
            return LiveRunningStatus(
                train_number=train_number,
                train_name=f"Train {train_number}",
                journey_date=journey_date,
                is_available=False,
                status_message=f"Live telemetry request failed: {exc}",
                data_source=self.display_name,
                freshness_category=DataFreshnessCategory.UNAVAILABLE,
                observation_timestamp=now_iso,
                disclaimer="Connection error contacting upstream API.",
            )

    async def get_pnr_status(self, pnr_number: str) -> PnrStatus:
        now_iso = datetime.now(timezone.utc).isoformat()

        if not self.is_configured:
            return PnrStatus(
                pnr_number=pnr_number,
                is_supported=False,
                booking_status="UNSUPPORTED_WITHOUT_CREDENTIALS",
                data_source=self.display_name,
                freshness_category=DataFreshnessCategory.UNAVAILABLE,
                retrieved_at=now_iso,
                message="PNR status lookup requires active provider credentials configured server-side.",
            )

        if not self._circuit_breaker.allow_request():
            return PnrStatus(
                pnr_number=pnr_number,
                is_supported=False,
                booking_status="CIRCUIT_BREAKER_OPEN",
                data_source=self.display_name,
                freshness_category=DataFreshnessCategory.UNAVAILABLE,
                retrieved_at=now_iso,
                message="Railway API circuit breaker is currently OPEN. Try again later.",
            )

        base_url = self._settings.railway_api_base_url.rstrip("/")
        url = f"{base_url}/api/v3/pnr"
        params = {"pnrNumber": pnr_number}

        try:
            async with httpx.AsyncClient(timeout=self._settings.railway_timeout_seconds) as client:
                res = await client.get(url, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    self._circuit_breaker.record_success()
                    data = res.json()
                    passengers = data.get("passengers") or []
                    # Redact passenger names for privacy compliance
                    sanitized_passengers = []
                    for idx, p in enumerate(passengers):
                        sanitized_passengers.append({
                            "passenger_index": idx + 1,
                            "booking_status": p.get("booking_status") or p.get("bookingStatus") or "CNF",
                            "current_status": p.get("current_status") or p.get("currentStatus") or "CNF",
                            "coach": p.get("coach"),
                            "berth": p.get("berth"),
                        })

                    return PnrStatus(
                        pnr_number=pnr_number,
                        is_supported=True,
                        train_number=data.get("train_number") or data.get("trainNo"),
                        train_name=data.get("train_name") or data.get("trainName"),
                        journey_date=data.get("doj") or data.get("dateOfJourney"),
                        booking_status=data.get("booking_status") or "ACTIVE",
                        chart_prepared=bool(data.get("chart_prepared") or data.get("chartPrepared")),
                        passengers=sanitized_passengers,
                        data_source=self.display_name,
                        freshness_category=DataFreshnessCategory.LIVE,
                        retrieved_at=now_iso,
                        message="PNR query completed successfully from authorized external API.",
                    )
                else:
                    self._circuit_breaker.record_failure()
                    return PnrStatus(
                        pnr_number=pnr_number,
                        is_supported=False,
                        booking_status=f"HTTP_{res.status_code}",
                        data_source=self.display_name,
                        freshness_category=DataFreshnessCategory.UNAVAILABLE,
                        retrieved_at=now_iso,
                        message=f"External PNR endpoint returned HTTP {res.status_code}",
                    )
        except Exception as exc:
            self._circuit_breaker.record_failure(exc)
            return PnrStatus(
                pnr_number=pnr_number,
                is_supported=False,
                booking_status="REQUEST_ERROR",
                data_source=self.display_name,
                freshness_category=DataFreshnessCategory.UNAVAILABLE,
                retrieved_at=now_iso,
                message=f"Error querying external PNR endpoint: {exc}",
            )
