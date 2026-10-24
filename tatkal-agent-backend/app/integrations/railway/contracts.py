"""
Railway Data Provider Contracts & Pydantic Schemas.

Defines standardized data models for:
- Station directory entries
- Train schedules and route stops
- Trains running between origin and destination stations
- Live running status observations
- PNR queries
- Provider capabilities and freshness metadata
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class DataFreshnessCategory(str, Enum):
    LIVE = "LIVE"
    CACHED = "CACHED"
    STATIC_DATASET = "STATIC_DATASET"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class Station(BaseModel):
    code: str = Field(..., description="Standard IR station code (e.g. NDLS)")
    name: str = Field(..., description="Full station name (e.g. New Delhi)")
    city: str = Field(..., description="City name")
    state: str = Field(..., description="State or territory")
    zone: str = Field(..., description="Indian Railways zonal code (e.g. NR, WR, CR)")


class StationStop(BaseModel):
    stop_number: int = Field(..., description="Sequential stop sequence number")
    station_code: str = Field(..., description="Station code")
    station_name: str = Field(..., description="Station name")
    arrival_time: str = Field(..., description="Arrival time HH:MM or SOURCE")
    departure_time: str = Field(..., description="Departure time HH:MM or DESTINATION")
    halt_minutes: int = Field(0, description="Halt duration in minutes")
    distance_km: int = Field(0, description="Distance from origin in kilometers")
    day_count: int = Field(1, description="Day of journey (1, 2, 3...)")


class TrainSchedule(BaseModel):
    train_number: str = Field(..., description="5-digit train number")
    train_name: str = Field(..., description="Official train name")
    origin_station_code: str = Field(..., description="Origin station code")
    origin_station_name: str = Field(..., description="Origin station name")
    destination_station_code: str = Field(..., description="Destination station code")
    destination_station_name: str = Field(..., description="Destination station name")
    runs_on_days: list[str] = Field(default_factory=list, description="Days of operation (Mon, Tue...)")
    available_classes: list[str] = Field(default_factory=list, description="Supported travel classes")
    stops: list[StationStop] = Field(default_factory=list, description="Chronological station stops")
    data_source: str = Field(..., description="Attributed provider or dataset identifier")
    freshness_category: DataFreshnessCategory = Field(
        DataFreshnessCategory.STATIC_DATASET,
        description="Freshness classification",
    )
    last_updated: str = Field(..., description="ISO timestamp of data retrieval or dataset version")


class TrainBetweenStations(BaseModel):
    train_number: str = Field(..., description="5-digit train number")
    train_name: str = Field(..., description="Train name")
    source_station_code: str = Field(..., description="Boarding station code")
    source_station_name: str = Field(..., description="Boarding station name")
    destination_station_code: str = Field(..., description="Destination station code")
    destination_station_name: str = Field(..., description="Destination station name")
    departure_time: str = Field(..., description="Departure time HH:MM")
    arrival_time: str = Field(..., description="Arrival time HH:MM")
    duration_minutes: int = Field(..., description="Travel duration in minutes")
    duration_formatted: str = Field(..., description="Formatted duration e.g. 15h 40m")
    available_classes: list[str] = Field(default_factory=list, description="Travel classes on this train")
    available_quotas: list[str] = Field(default_factory=list, description="Eligible booking quotas")
    base_fare: Optional[float] = Field(None, description="Official base fare in INR if available")
    tatkal_charge: Optional[float] = Field(None, description="Calculated Tatkal surcharge in INR if applicable")
    total_fare: Optional[float] = Field(None, description="Total fare in INR if available")
    availability_status: Optional[str] = Field(None, description="Availability description or quota label")
    data_source: str = Field(..., description="Attributed data source name")
    freshness_category: DataFreshnessCategory = Field(..., description="Freshness classification")
    retrieved_at: str = Field(..., description="ISO timestamp when record was generated/cached")
    notes: Optional[str] = Field(None, description="Context notes regarding fares or availability")


class LiveRunningStatus(BaseModel):
    train_number: str = Field(..., description="Train number")
    train_name: str = Field(..., description="Train name")
    journey_date: str = Field(..., description="Journey start date YYYY-MM-DD")
    is_available: bool = Field(..., description="Whether live telemetry is supported and available")
    current_station_code: Optional[str] = Field(None, description="Last reported station code")
    current_station_name: Optional[str] = Field(None, description="Last reported station name")
    delay_departure_minutes: int = Field(0, description="Departure delay in minutes")
    delay_arrival_minutes: int = Field(0, description="Arrival delay in minutes")
    status_message: str = Field(..., description="Truthful operational status message")
    last_reported_time: Optional[str] = Field(None, description="Last reported time from provider")
    is_terminated: bool = Field(False, description="Whether journey has completed")
    data_source: str = Field(..., description="Data provider identifier")
    freshness_category: DataFreshnessCategory = Field(..., description="Freshness classification")
    observation_timestamp: str = Field(..., description="ISO timestamp of observation")
    disclaimer: str = Field(..., description="Honest compliance & GPS source disclosure")


class PnrStatus(BaseModel):
    pnr_number: str = Field(..., description="10-digit Indian Railways PNR number")
    is_supported: bool = Field(..., description="Whether PNR query is supported by configured provider")
    train_number: Optional[str] = Field(None, description="Booked train number")
    train_name: Optional[str] = Field(None, description="Booked train name")
    journey_date: Optional[str] = Field(None, description="Journey date YYYY-MM-DD")
    booking_status: str = Field(..., description="Booking status description")
    chart_prepared: bool = Field(False, description="Whether reservation chart is prepared")
    passengers: list[dict[str, Any]] = Field(default_factory=list, description="Passenger booking statuses")
    data_source: str = Field(..., description="Provider source identifier")
    freshness_category: DataFreshnessCategory = Field(..., description="Freshness classification")
    retrieved_at: str = Field(..., description="ISO timestamp of response")
    message: str = Field(..., description="Result or policy explanation")


class ProviderCapabilities(BaseModel):
    provider_id: str = Field(..., description="Unique provider key (e.g. static_dataset, rapidapi)")
    display_name: str = Field(..., description="Human-readable provider title")
    has_station_search: bool = Field(..., description="Supports station search")
    has_timetable: bool = Field(..., description="Supports full train timetables")
    has_trains_between: bool = Field(..., description="Supports querying trains between stations")
    has_live_running: bool = Field(..., description="Supports live GPS train running telemetry")
    has_fare: bool = Field(..., description="Supports genuine fare lookups")
    has_availability: bool = Field(..., description="Supports live seat availability")
    has_pnr: bool = Field(..., description="Supports PNR status queries")
    auth_configured: bool = Field(..., description="Whether required credentials are configured server-side")
    quota_limits: str = Field(..., description="Rate limit or quota description")
    notes: str = Field(..., description="Licensing, source, or operational constraints")


class ProviderStatusResponse(BaseModel):
    active_mode: str = Field(..., description="Current configured operating mode: hybrid, static, rapidapi")
    providers: list[ProviderCapabilities] = Field(default_factory=list, description="Registered providers")
    cache_entries_count: int = Field(0, description="Active cached response items")
    cache_stats: dict[str, Any] = Field(default_factory=dict, description="Cache hit/miss metrics")
