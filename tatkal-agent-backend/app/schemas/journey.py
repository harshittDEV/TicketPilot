"""
Journey configuration schemas for the Autonomous Tatkal Booking Agent.

Defines:
- Passenger details schema with validation (1-4 passengers for Tatkal, valid age, gender, berth).
- Booking preferences (alternative trains, alternative classes, max fare).
- Scheduling configuration (journey date, travel class, quota, Tatkal opening calculation).
- Preparation report schema detailing all 12 backend pre-flight checks.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class QuotaType(str, Enum):
    """Railway booking quotas."""
    TATKAL = "TATKAL"
    PREMIUM_TATKAL = "PREMIUM_TATKAL"
    GENERAL = "GENERAL"
    LADIES = "LADIES"


class Gender(str, Enum):
    """Passenger gender."""
    MALE = "M"
    FEMALE = "F"
    TRANSGENDER = "T"


class BerthPreference(str, Enum):
    """Train berth preferences."""
    NO_PREFERENCE = "NONE"
    LOWER = "LB"
    MIDDLE = "MB"
    UPPER = "UB"
    SIDE_LOWER = "SL"
    SIDE_UPPER = "SU"
    WINDOW_SIDE = "WS"


class PassengerDetails(BaseModel):
    """Passenger details for railway reservation."""
    name: str = Field(..., min_length=2, max_length=60, description="Full passenger name as per ID")
    age: int = Field(..., ge=1, le=125, description="Age in completed years")
    gender: Gender = Field(default=Gender.MALE, description="Passenger gender (M, F, T)")
    berth_preference: BerthPreference = Field(
        default=BerthPreference.NO_PREFERENCE, description="Berth or seat preference"
    )
    senior_citizen_concession: bool = Field(
        default=False, description="Opt-in for senior citizen concession if eligible"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Passenger name cannot be blank")
        # Ensure name contains alphabetic characters
        if not any(c.isalpha() for c in cleaned):
            raise ValueError("Passenger name must contain alphabetic characters")
        return cleaned


class BookingPreferences(BaseModel):
    """User preferences and constraints for journey booking."""
    preferred_train_number: Optional[str] = Field(None, description="Primary train number (5 digits)")
    preferred_train_name: Optional[str] = Field(None, description="Primary train name")
    alternative_train_numbers: list[str] = Field(
        default_factory=list, description="Alternative train numbers in order of priority"
    )
    preferred_class: str = Field(default="3A", description="Preferred travel class (e.g., '3A', '2A', 'SL')")
    alternative_classes: list[str] = Field(
        default_factory=list, description="Acceptable alternative classes in order of preference"
    )
    allow_alternative_train: bool = Field(
        default=True, description="Whether the agent may select an alternative train if preferred is unavailable"
    )
    allow_alternative_class: bool = Field(
        default=False, description="Whether the agent may choose an alternative class"
    )
    max_acceptable_fare: Optional[float] = Field(
        None, ge=0.0, description="Maximum acceptable fare per passenger (INR)"
    )


class SchedulingPreferences(BaseModel):
    """Scheduling and timing configuration."""
    journey_date: str = Field(..., description="Date of journey (YYYY-MM-DD)")
    travel_class: str = Field(default="3A", description="Travel class for quota timing calculation")
    quota: QuotaType = Field(default=QuotaType.TATKAL, description="Booking quota (TATKAL / GENERAL)")
    reminder_minutes_before: int = Field(
        default=15, ge=1, le=60, description="Minutes before opening to start pre-flight preparation"
    )
    execute_once: bool = Field(default=True, description="Whether to execute only once")
    scheduled_opening_ist: Optional[str] = Field(None, description="Calculated Tatkal opening time in IST")
    scheduled_opening_utc: Optional[str] = Field(None, description="Calculated Tatkal opening time in UTC")
    preparation_trigger_time_utc: Optional[str] = Field(
        None, description="Timestamp when preparation workflow should trigger"
    )


class JourneyConfiguration(BaseModel):
    """Complete journey configuration payload stored in task configuration."""
    source_station: str = Field(..., min_length=2, max_length=100, description="Origin station name or code")
    destination_station: str = Field(..., min_length=2, max_length=100, description="Destination station name or code")
    journey_date: str = Field(..., description="Journey departure date (YYYY-MM-DD)")
    travel_class: str = Field(default="3A", description="Booking travel class")
    quota: QuotaType = Field(default=QuotaType.TATKAL, description="Booking quota")
    passengers: list[PassengerDetails] = Field(
        default_factory=list, min_length=1, max_length=6, description="List of passengers (1-4 for Tatkal)"
    )
    preferences: BookingPreferences = Field(
        default_factory=BookingPreferences, description="Train and class preferences"
    )
    scheduling: Optional[SchedulingPreferences] = None
    credential_ref: Optional[str] = Field(
        None, description="Opaque token reference in SecureCredentialStore for booking credentials"
    )

    @field_validator("passengers")
    @classmethod
    def validate_passenger_count_for_tatkal(cls, v: list[PassengerDetails], info) -> list[PassengerDetails]:
        if len(v) < 1:
            raise ValueError("At least 1 passenger is required")
        # In Indian Railways, Tatkal rules limit bookings to maximum 4 passengers per PNR
        if len(v) > 4:
            raise ValueError("Tatkal quota bookings are restricted to a maximum of 4 passengers per PNR")
        return v

    @field_validator("journey_date")
    @classmethod
    def validate_journey_date(cls, v: str) -> str:
        try:
            dep_date = date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"Invalid journey_date '{v}'. Expected YYYY-MM-DD format.") from exc
        return v


class CheckResult(BaseModel):
    """Result of an individual pre-flight preparation check."""
    check_id: int
    name: str
    passed: bool
    status: str  # 'PASSED', 'WARNING', 'FAILED', 'INFO'
    details: str
    data_source: Optional[str] = None
    freshness: Optional[str] = None


class PreparationReport(BaseModel):
    """Structured report returned by the 12-point preparation workflow."""
    task_id: str
    prepared_at: str
    overall_ready: bool
    unresolved_prerequisites: list[str] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    resolved_source_station: Optional[dict[str, Any]] = None
    resolved_dest_station: Optional[dict[str, Any]] = None
    eligible_trains_count: int = 0
    top_train: Optional[dict[str, Any]] = None
    tatkal_timings: Optional[dict[str, Any]] = None
    execution_plan: list[dict[str, Any]] = Field(default_factory=list)
    requires_human_at_steps: list[str] = Field(default_factory=list)
