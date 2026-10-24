"""
Train comparison integration adapter.

Implements the TrainComparisonIntegration protocol (contracts.py).
Integrates Member 4's train ranking algorithm (trainRanker.js) with the backend
contract and provides data-provider hooks.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.agent.recovery import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerRegistry,
    CircuitState,
)
from app.integrations.contracts import (
    TrainCandidate,
    TrainComparisonIntegration,
    TrainComparisonResult,
    TrainQuery,
)
from app.integrations.train_comparison.ranker import rank_trains

logger = logging.getLogger(__name__)

# Default sample trains for Roorkee -> Haridwar to support Member 4 verification out-of-the-box
DEFAULT_TRAIN_CATALOG: list[dict[str, Any]] = [
    {
        "trainNumber": "12001",
        "trainName": "Shatabdi Express",
        "origin": "Roorkee",
        "destination": "Haridwar",
        "departureTime": "06:15",
        "arrivalTime": "07:00",
        "quota": "TATKAL",
        "eligible": True,
        "availabilityVerified": True,
        "totalFare": 450.0,
        "durationMinutes": 45,
        "availableClasses": ["CC", "EC"],
        "availabilityStatus": "AVAILABLE-12",
    },
    {
        "trainNumber": "12002",
        "trainName": "Jan Shatabdi",
        "origin": "Roorkee",
        "destination": "Haridwar",
        "departureTime": "08:30",
        "arrivalTime": "09:30",
        "quota": "TATKAL",
        "eligible": True,
        "availabilityVerified": True,
        "totalFare": 380.0,
        "durationMinutes": 60,
        "availableClasses": ["2S", "CC"],
        "availabilityStatus": "AVAILABLE-24",
    },
    {
        "trainNumber": "12003",
        "trainName": "Hemkunt Express",
        "origin": "Roorkee",
        "destination": "Haridwar",
        "departureTime": "15:00",
        "arrivalTime": "15:40",
        "quota": "TATKAL",
        "eligible": True,
        "availabilityVerified": False,  # Unverified availability
        "totalFare": 200.0,
        "durationMinutes": 40,
        "availableClasses": ["SL", "3A"],
        "availabilityStatus": "WL-5",
    },
]


class TrainComparisonAdapter:
    """
    Adapter implementing the TrainComparisonIntegration protocol.

    Finds and ranks trains for a given route and quota using Member 4's
    verified availability and price-first sorting logic.
    """

    def __init__(
        self,
        catalog: Optional[list[dict[str, Any]]] = None,
        data_provider: Optional[Callable[[TrainQuery], list[dict[str, Any]]]] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self._catalog = list(catalog) if catalog is not None else list(DEFAULT_TRAIN_CATALOG)
        self._data_provider = data_provider
        self._circuit_breaker = (
            circuit_breaker
            if circuit_breaker is not None
            else CircuitBreakerRegistry.get("train_comparison")
        )

    def set_catalog(self, catalog: list[dict[str, Any]]) -> None:
        """Override the train catalog (useful for testing)."""
        self._catalog = list(catalog)

    def add_train(self, train: dict[str, Any]) -> None:
        """Add a train option to the catalog."""
        self._catalog.append(train)

    async def find_trains(self, query: TrainQuery) -> TrainComparisonResult:
        """
        Request and rank eligible train options for the given query.
        """
        logger.info(
            "Searching trains: %s -> %s on %s (quota=%s, class=%s)",
            query.source_station,
            query.destination_station,
            query.travel_date,
            query.quota,
            query.travel_class,
        )

        # 1. Fetch raw candidates (circuit-breaker protected if external provider configured)
        if self._data_provider:
            if self._circuit_breaker and not self._circuit_breaker.allow_request():
                raise CircuitBreakerOpenError(
                    breaker_name=self._circuit_breaker.name,
                    cooldown_remaining=self._circuit_breaker.cooldown_remaining,
                )
            try:
                raw_trains = self._data_provider(query)
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()
            except Exception as exc:
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure(exc)
                raise
        else:
            raw_trains = self._catalog

        # 2. Filter and rank using Member 4's algorithm
        rank_result = rank_trains(
            raw_trains,
            origin=query.source_station,
            destination=query.destination_station,
            quota=query.quota,
        )

        # 3. If catalog had no matches and no custom data_provider was passed, query RailwayDataService
        if not rank_result["ranked"] and self._data_provider is None:
            try:
                from app.integrations.railway.service import get_railway_service
                railway_svc = get_railway_service()
                real_trains = await railway_svc.get_trains_between(
                    source=query.source_station,
                    destination=query.destination_station,
                    journey_date=query.travel_date,
                    travel_class=query.travel_class,
                )
                if real_trains:
                    adapted_trains = []
                    for rt in real_trains:
                        adapted_trains.append({
                            "trainNumber": rt.train_number,
                            "trainName": rt.train_name,
                            "origin": query.source_station,
                            "destination": query.destination_station,
                            "departureTime": rt.departure_time,
                            "arrivalTime": rt.arrival_time,
                            "quota": query.quota,
                            "eligible": True,
                            "availabilityVerified": True,
                            "totalFare": rt.total_fare if rt.total_fare is not None else 1500.0,
                            "durationMinutes": rt.duration_minutes,
                            "availableClasses": rt.available_classes,
                            "availabilityStatus": rt.availability_status or "AVAILABLE",
                        })
                    rank_result = rank_trains(
                        adapted_trains,
                        origin=query.source_station,
                        destination=query.destination_station,
                        quota=query.quota,
                    )
            except Exception as exc:
                logger.warning("Railway service lookup during train comparison failed: %s", exc)

        ranked_items = rank_result["ranked"]
        candidates: list[TrainCandidate] = []

        for item in ranked_items:
            # Map item to TrainCandidate schema
            train_num = str(item.get("trainNumber") or item.get("train_number") or "")
            train_name = str(item.get("trainName") or item.get("train_name") or f"Train {train_num}")
            dep_time = str(item.get("departureTime") or item.get("departure_time") or "00:00")
            arr_time = str(item.get("arrivalTime") or item.get("arrival_time") or "00:00")
            avail_classes = list(item.get("availableClasses") or item.get("available_classes") or [])
            avail_status = str(item.get("availabilityStatus") or item.get("availability_status") or "")
            fare = float(item["totalFare"]) if "totalFare" in item else (float(item["fare"]) if "fare" in item else None)

            # Metadata preserves additional details without violating schema
            meta: dict[str, Any] = {
                "duration_minutes": item.get("durationMinutes") or item.get("duration_minutes"),
                "is_selected": (item == rank_result["selected"]),
            }

            candidates.append(
                TrainCandidate(
                    train_number=train_num,
                    train_name=train_name,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    available_classes=avail_classes,
                    availability_status=avail_status,
                    fare=fare,
                    metadata=meta,
                )
            )

        msg = (
            f"Found {len(candidates)} verified eligible train(s)"
            if candidates
            else "No verified eligible trains found for query"
        )

        return TrainComparisonResult(
            query=query,
            candidates=candidates,
            message=msg,
        )

    async def health_check(self) -> bool:
        """Return True if train catalog / provider is available and circuit is not open."""
        if self._circuit_breaker and self._circuit_breaker.state == CircuitState.OPEN:
            return False
        return True

    def get_metadata(self) -> dict[str, Any]:
        """Return metadata describing the train comparison capabilities."""
        meta: dict[str, Any] = {
            "name": "train_comparison",
            "version": "1.0.0",
            "description": "Train candidate filtering and price-optimized ranking",
            "catalog_size": len(self._catalog),
            "supported_quotas": ["TATKAL", "GENERAL"],
        }
        if self._circuit_breaker:
            meta["circuit_breaker"] = self._circuit_breaker.get_metrics()
        return meta
