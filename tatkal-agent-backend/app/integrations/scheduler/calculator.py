"""
Tatkal opening time calculator.

Adapted from Member 3's scheduler implementation (Scheduler/TicketPilot-feature-member-3-scheduler/scheduler.js).
Implements IRCTC Tatkal booking rules:
- AC classes (2A, 3A, CC, EC, 3E): Booking opens at 10:00 AM IST on the day prior to departure from train origin.
- Non-AC classes (SL, FC, 2S): Booking opens at 11:00 AM IST on the day prior to departure from train origin.
- Explicit timezone handling using Asia/Kolkata (IST = UTC+05:30).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# Tatkal opening times in IST by travel class code
CLASS_TIMES: dict[str, str] = {
    "2A": "10:00",
    "3A": "10:00",
    "CC": "10:00",
    "EC": "10:00",
    "3E": "10:00",
    "SL": "11:00",
    "FC": "11:00",
    "2S": "11:00",
}


def get_opening_time_for_class(travel_class: str) -> str:
    """
    Return the Tatkal opening time string (HH:MM in IST) for the given class.

    Raises:
        ValueError: If travel_class is not a recognized Tatkal booking class.
    """
    code = travel_class.upper().strip()
    if code not in CLASS_TIMES:
        supported = ", ".join(sorted(CLASS_TIMES.keys()))
        raise ValueError(
            f"Unsupported Tatkal travel class '{travel_class}'. Must be one of: {supported}"
        )
    return CLASS_TIMES[code]


def calculate_tatkal_schedule(
    journey_origin_departure_date: str,
    travel_class: str,
    reminder_minutes_before: int = 5,
) -> dict[str, Any]:
    """
    Calculate the Tatkal opening instant and pre-alert time.

    Args:
        journey_origin_departure_date: Date train departs from origin station (YYYY-MM-DD).
        travel_class: Travel class code (e.g. 'SL', '3A', '2A').
        reminder_minutes_before: Minutes before opening to fire pre-alert (default: 5).

    Returns:
        dict containing exact ISO strings for opening and pre-alert in both IST and UTC.

    Raises:
        ValueError: If date format or class code is invalid.
    """
    # 1. Parse departure date
    try:
        dep_date = date.fromisoformat(journey_origin_departure_date)
    except ValueError as exc:
        raise ValueError(
            f"Invalid journey date format '{journey_origin_departure_date}'. Expected YYYY-MM-DD."
        ) from exc

    # 2. Tatkal booking opens 1 day prior to origin departure date
    opening_date = dep_date - timedelta(days=1)

    # 3. Lookup opening time
    class_code = travel_class.upper().strip()
    opening_time_str = get_opening_time_for_class(class_code)
    hour, minute = map(int, opening_time_str.split(":"))

    # 4. Construct IST opening datetime
    opening_ist = datetime.combine(opening_date, time(hour, minute), tzinfo=IST)
    opening_utc = opening_ist.astimezone(UTC)

    # 5. Calculate pre-alert instant
    pre_alert_ist = opening_ist - timedelta(minutes=reminder_minutes_before)
    pre_alert_utc = pre_alert_ist.astimezone(UTC)

    return {
        "class_code": class_code,
        "journey_origin_departure_date": dep_date.isoformat(),
        "opening_date": opening_date.isoformat(),
        "opening_time_ist": opening_time_str,
        "opening_datetime_ist": opening_ist.isoformat(),
        "opening_datetime_utc": opening_utc.isoformat(),
        "pre_alert_datetime_ist": pre_alert_ist.isoformat(),
        "pre_alert_datetime_utc": pre_alert_utc.isoformat(),
        "reminder_minutes_before": reminder_minutes_before,
    }
