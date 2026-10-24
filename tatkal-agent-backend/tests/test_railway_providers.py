"""
Tests for Railway Data Providers, Caching, and API Endpoints (Phase 9).

Verifies:
- Station directory search and lookup
- Train timetable lookup and intermediate stop parsing
- Trains between stations query and failover
- Live running status truthful unsupported states
- PNR status validation and privacy protections
- Caching behavior and freshness attribution
- Provider status reporting
- Integration with TrainComparisonAdapter
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.integrations.contracts import TrainQuery
from app.integrations.railway.cache_manager import get_cache_manager
from app.integrations.railway.contracts import DataFreshnessCategory
from app.integrations.railway.service import get_railway_service
from app.integrations.railway.station_directory import (
    get_station_by_code,
    normalize_station_input,
    search_stations,
)
from app.integrations.train_comparison.adapter import TrainComparisonAdapter
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clear_railway_cache():
    cache = get_cache_manager()
    cache.clear()
    yield
    cache.clear()


class TestStationDirectory:
    """Verify in-memory station directory functionality."""

    def test_normalize_station_input(self):
        assert normalize_station_input("NDLS - New Delhi") == "NDLS"
        assert normalize_station_input("bct") == "BCT"
        assert normalize_station_input("  hwh - Howrah  ") == "HWH"

    def test_get_station_by_code(self):
        stn = get_station_by_code("NDLS")
        assert stn is not None
        assert stn.code == "NDLS"
        assert stn.name == "New Delhi"
        assert stn.zone == "NR"

    def test_get_unknown_station(self):
        assert get_station_by_code("XYZ999") is None

    def test_search_stations_by_code(self):
        results = search_stations("NDLS")
        assert len(results) > 0
        assert results[0].code == "NDLS"

    def test_search_stations_by_city(self):
        results = search_stations("Mumbai", limit=5)
        assert len(results) > 0
        codes = [s.code for s in results]
        assert any(c in ["MMCT", "BCT", "CSMT", "BDTS", "LTT"] for c in codes)

    def test_search_stations_no_results(self):
        results = search_stations("NONEXISTENT_STATION_QUERY")
        assert len(results) == 0

    def test_search_stations_empty_query_returns_popular(self):
        results = search_stations("", limit=5)
        assert len(results) == 5
        assert results[0].code == "NDLS"


class TestRailwayService:
    """Verify RailwayDataService orchestrator and caching."""

    @pytest.mark.asyncio
    async def test_get_trains_between_stations(self):
        service = get_railway_service()
        trains = await service.get_trains_between(
            source="NDLS",
            destination="MMCT",
            journey_date="2026-11-01",
            travel_class="3A",
        )
        assert len(trains) > 0
        train_nums = [t.train_number for t in trains]
        assert "12952" in train_nums
        rajdhani = next(t for t in trains if t.train_number == "12952")
        assert rajdhani.source_station_code == "NDLS"
        assert rajdhani.destination_station_code == "MMCT"
        assert rajdhani.total_fare == 2550.0  # 2150 base + 400 tatkal
        assert rajdhani.freshness_category == DataFreshnessCategory.STATIC_DATASET

    @pytest.mark.asyncio
    async def test_caching_returns_cached_freshness(self):
        service = get_railway_service()
        trains_first = await service.get_trains_between(
            source="NDLS",
            destination="MMCT",
            journey_date="2026-11-01",
        )
        assert len(trains_first) > 0
        # Second call should hit cache and be tagged CACHED
        trains_second = await service.get_trains_between(
            source="NDLS",
            destination="MMCT",
            journey_date="2026-11-01",
        )
        assert len(trains_second) == len(trains_first)
        assert trains_second[0].freshness_category == DataFreshnessCategory.CACHED

    @pytest.mark.asyncio
    async def test_get_train_schedule(self):
        service = get_railway_service()
        schedule = await service.get_train_schedule("12952")
        assert schedule is not None
        assert schedule.train_number == "12952"
        assert len(schedule.stops) == 7
        assert schedule.stops[0].station_code == "NDLS"
        assert schedule.stops[-1].station_code == "MMCT"

    @pytest.mark.asyncio
    async def test_get_unknown_train_schedule(self):
        service = get_railway_service()
        schedule = await service.get_train_schedule("99999")
        assert schedule is None

    @pytest.mark.asyncio
    async def test_live_running_status_truthful_without_api_key(self):
        service = get_railway_service()
        live = await service.get_live_running_status("12952", "2026-11-01")
        assert live.train_number == "12952"
        assert live.is_available is False
        assert live.freshness_category == DataFreshnessCategory.UNAVAILABLE
        assert "requires active GPS provider credentials" in live.status_message

    @pytest.mark.asyncio
    async def test_pnr_status_truthful_without_api_key(self):
        service = get_railway_service()
        pnr = await service.get_pnr_status("1234567890")
        assert pnr.pnr_number == "1234567890"
        assert pnr.is_supported is False
        assert pnr.freshness_category == DataFreshnessCategory.UNAVAILABLE

    def test_provider_status_reporting(self):
        service = get_railway_service()
        status_resp = service.get_provider_status()
        assert status_resp.active_mode in ["hybrid", "static", "rapidapi"]
        assert len(status_resp.providers) >= 2
        provider_ids = [p.provider_id for p in status_resp.providers]
        assert "static_dataset" in provider_ids
        assert "rapidapi" in provider_ids


class TestRailwayApiEndpoints:
    """Verify HTTP endpoints under /api/v1/railway."""

    def test_search_stations_endpoint(self, client: TestClient):
        res = client.get("/api/v1/railway/stations?q=NDLS&limit=5")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert len(body["data"]) > 0
        assert body["data"][0]["code"] == "NDLS"

    def test_get_station_details_endpoint(self, client: TestClient):
        res = client.get("/api/v1/railway/stations/BCT")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["code"] == "BCT"

    def test_get_station_details_not_found(self, client: TestClient):
        res = client.get("/api/v1/railway/stations/NONEXISTENT")
        assert res.status_code == 404

    def test_get_trains_between_endpoint(self, client: TestClient):
        res = client.get("/api/v1/railway/trains/between?from_station=NDLS&to_station=MMCT&date=2026-11-01&travel_class=3A")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert len(body["data"]) > 0
        assert any(t["train_number"] == "12952" for t in body["data"])

    def test_get_trains_between_same_station_rejected(self, client: TestClient):
        res = client.get("/api/v1/railway/trains/between?from_station=NDLS&to_station=NDLS&date=2026-11-01")
        assert res.status_code == 400

    def test_get_train_schedule_endpoint(self, client: TestClient):
        res = client.get("/api/v1/railway/trains/12952/schedule")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["train_number"] == "12952"
        assert len(body["data"]["stops"]) == 7

    def test_get_train_schedule_not_found(self, client: TestClient):
        res = client.get("/api/v1/railway/trains/999999/schedule")
        assert res.status_code == 404

    def test_get_live_running_status_endpoint(self, client: TestClient):
        res = client.get("/api/v1/railway/trains/12952/live?date=2026-11-01")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["train_number"] == "12952"
        assert body["data"]["is_available"] is False

    def test_get_pnr_status_invalid_format(self, client: TestClient):
        res = client.get("/api/v1/railway/pnr/123")
        assert res.status_code == 400

    def test_get_pnr_status_valid_10_digits(self, client: TestClient):
        res = client.get("/api/v1/railway/pnr/2849182371")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["data"]["pnr_number"] == "2849182371"

    def test_get_provider_status_endpoint(self, client: TestClient):
        res = client.get("/api/v1/railway/providers/status")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "providers" in body["data"]


class TestTrainComparisonAdapterIntegration:
    """Verify TrainComparisonAdapter correctly discovers real railway trains."""

    @pytest.mark.asyncio
    async def test_find_trains_delhi_to_mumbai_uses_real_railway_data(self):
        adapter = TrainComparisonAdapter()
        query = TrainQuery(
            source_station="NDLS - New Delhi",
            destination_station="BCT - Mumbai Central",
            travel_date="2026-11-01",
            travel_class="3A",
            quota="TATKAL",
        )
        res = await adapter.find_trains(query)
        assert len(res.candidates) > 0
        candidate_numbers = [c.train_number for c in res.candidates]
        assert "12952" in candidate_numbers
        # Top candidate should be selected and ranked by fare/duration
        top = res.candidates[0]
        assert top.fare is not None
        assert top.departure_time != "00:00"

    @pytest.mark.asyncio
    async def test_find_trains_roorkee_to_haridwar_preserves_catalog_compatibility(self):
        adapter = TrainComparisonAdapter()
        query = TrainQuery(
            source_station="Roorkee",
            destination_station="Haridwar",
            travel_date="2026-11-01",
            quota="TATKAL",
        )
        res = await adapter.find_trains(query)
        assert len(res.candidates) == 2  # 12002 (380) and 12001 (450)
        assert res.candidates[0].train_number == "12002"
