"""
Tests for Train Comparison ranking algorithms and adapter (Member 4).
"""

import pytest

from app.integrations.contracts import TrainQuery
from app.integrations.train_comparison.adapter import TrainComparisonAdapter
from app.integrations.train_comparison.ranker import rank_trains

# Sample trains matching Member 4 test fixture
SAMPLE_TRAINS = [
    {
        "trainNumber": "12001",
        "origin": "Roorkee",
        "destination": "Haridwar",
        "quota": "TATKAL",
        "eligible": True,
        "availabilityVerified": True,
        "totalFare": 450,
        "durationMinutes": 45,
    },
    {
        "trainNumber": "12002",
        "origin": "Roorkee",
        "destination": "Haridwar",
        "quota": "TATKAL",
        "eligible": True,
        "availabilityVerified": True,
        "totalFare": 380,
        "durationMinutes": 60,
    },
    {
        "trainNumber": "12003",
        "origin": "Roorkee",
        "destination": "Haridwar",
        "quota": "TATKAL",
        "eligible": True,
        "availabilityVerified": False,
        "totalFare": 200,
        "durationMinutes": 40,
    },
]


class TestTrainRankingAlgorithm:
    """Verify train ranking behavior adapted from Member 4's trainRanker.test.js."""

    def test_selects_cheapest_verified_eligible_train(self):
        result = rank_trains(SAMPLE_TRAINS)
        assert result["status"] == "OPTIONS_FOUND"
        assert result["selected"]["trainNumber"] == "12002"
        assert result["selected"]["totalFare"] == 380

    def test_rejects_unverified_availability(self):
        result = rank_trains([SAMPLE_TRAINS[2]])
        assert result["selected"] is None
        assert result["status"] == "NO_VERIFIED_OPTIONS"

    def test_handles_empty_train_list(self):
        result = rank_trains([])
        assert result["selected"] is None
        assert len(result["ranked"]) == 0
        assert result["status"] == "NO_VERIFIED_OPTIONS"

    def test_rejects_invalid_input(self):
        with pytest.raises(TypeError, match="Expected an array/list"):
            rank_trains(None)  # type: ignore

    def test_rejects_missing_and_invalid_fares(self):
        invalid_trains = [
            {
                **SAMPLE_TRAINS[0],
                "trainNumber": "20001",
                "totalFare": None,
            },
            {
                **SAMPLE_TRAINS[0],
                "trainNumber": "20002",
                "totalFare": -50,
            },
        ]
        result = rank_trains(invalid_trains)
        assert result["selected"] is None

    def test_rejects_trains_with_wrong_route_or_quota(self):
        wrong_route = {
            **SAMPLE_TRAINS[0],
            "destination": "Delhi",
        }
        wrong_quota = {
            **SAMPLE_TRAINS[1],
            "quota": "GENERAL",
        }
        result = rank_trains([wrong_route, wrong_quota])
        assert result["selected"] is None

    def test_uses_shorter_duration_when_fares_are_equal(self):
        slower = {
            **SAMPLE_TRAINS[0],
            "trainNumber": "20010",
            "totalFare": 400,
            "durationMinutes": 90,
        }
        faster = {
            **SAMPLE_TRAINS[1],
            "trainNumber": "20011",
            "totalFare": 400,
            "durationMinutes": 45,
        }
        result = rank_trains([slower, faster])
        assert result["selected"]["trainNumber"] == "20011"


class TestTrainComparisonAdapter:
    """Verify TrainComparisonAdapter integration protocol implementation."""

    @pytest.mark.asyncio
    async def test_find_trains_returns_structured_candidates(self):
        adapter = TrainComparisonAdapter()
        query = TrainQuery(
            source_station="Roorkee",
            destination_station="Haridwar",
            travel_date="2026-11-20",
            quota="TATKAL",
        )
        res = await adapter.find_trains(query)

        assert res.query.source_station == "Roorkee"
        assert len(res.candidates) >= 2
        # First candidate is the cheapest (12002 @ 380)
        assert res.candidates[0].train_number == "12002"
        assert res.candidates[0].fare == 380.0
        # Second candidate is 12001 @ 450
        assert res.candidates[1].train_number == "12001"
        assert res.candidates[1].fare == 450.0

    @pytest.mark.asyncio
    async def test_find_trains_empty_for_unserved_route(self):
        adapter = TrainComparisonAdapter()
        query = TrainQuery(
            source_station="Mumbai",
            destination_station="Kolkata",
            travel_date="2026-11-20",
        )
        res = await adapter.find_trains(query)
        assert len(res.candidates) == 0
        assert "No verified eligible trains" in res.message

    @pytest.mark.asyncio
    async def test_health_check_and_metadata(self):
        adapter = TrainComparisonAdapter()
        assert await adapter.health_check() is True
        meta = adapter.get_metadata()
        assert meta["name"] == "train_comparison"
        assert meta["catalog_size"] >= 3
