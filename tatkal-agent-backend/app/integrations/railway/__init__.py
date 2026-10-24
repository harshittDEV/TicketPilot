"""
Railway Data Provider Package (Phase 9).

Provides legitimate railway data integrations:
- Verified Indian Railway Station Directory (80+ major hubs, codes, zones).
- Official open-data static timetables, stops, and schedules.
- Documented external API integration (RapidAPI / Indian Railways) with header auth.
- Transparent caching, freshness attribution, rate limiting, and failover.
"""

from app.integrations.railway.contracts import (
    DataFreshnessCategory,
    LiveRunningStatus,
    PnrStatus,
    ProviderCapabilities,
    ProviderStatusResponse,
    Station,
    StationStop,
    TrainBetweenStations,
    TrainSchedule,
)
from app.integrations.railway.service import RailwayDataService, get_railway_service

__all__ = [
    "DataFreshnessCategory",
    "LiveRunningStatus",
    "PnrStatus",
    "ProviderCapabilities",
    "ProviderStatusResponse",
    "RailwayDataService",
    "Station",
    "StationStop",
    "TrainBetweenStations",
    "TrainSchedule",
    "get_railway_service",
]
