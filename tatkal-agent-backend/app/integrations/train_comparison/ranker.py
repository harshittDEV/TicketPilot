"""
Train ranking algorithms adapted from Member 4's trainRanker.js.

Filters and ranks train candidates based on:
1. Eligibility & verified availability.
2. Route and Tatkal quota match.
3. Total fare (cheapest first).
4. Duration in minutes (shortest first).
5. Train number tie-breaker (alphanumeric order).
"""

from __future__ import annotations

import math
from typing import Any


def _is_finite_number(val: Any) -> bool:
    """Return True if val is a finite int or float."""
    if isinstance(val, (int, float)):
        return not math.isnan(val) and not math.isinf(val)
    return False


def _get_field(train: dict[str, Any], *names: str, default: Any = None) -> Any:
    """Extract a field trying camelCase and snake_case aliases."""
    for name in names:
        if name in train:
            return train[name]
    return default


def rank_trains(
    trains: list[dict[str, Any]],
    origin: str = "Roorkee",
    destination: str = "Haridwar",
    quota: str = "TATKAL",
) -> dict[str, Any]:
    """
    Filter and rank train options according to Member 4's specification.

    Args:
        trains: List of train option dictionaries.
        origin: Expected origin station (default: "Roorkee").
        destination: Expected destination station (default: "Haridwar").
        quota: Expected quota (default: "TATKAL").

    Returns:
        dict containing:
            - "selected": Top-ranked train option or None
            - "ranked": List of all eligible trains sorted by priority
            - "status": "OPTIONS_FOUND" | "NO_VERIFIED_OPTIONS"

    Raises:
        TypeError: If trains is not a list.
    """
    if not isinstance(trains, list):
        raise TypeError("Expected an array/list of train options")

    eligible: list[dict[str, Any]] = []

    for train in trains:
        if not isinstance(train, dict):
            continue

        train_num = _get_field(train, "trainNumber", "train_number")
        if not train_num:
            continue

        train_origin = _get_field(train, "origin", "source_station")
        train_dest = _get_field(train, "destination", "destination_station")
        train_quota = _get_field(train, "quota")
        is_eligible = _get_field(train, "eligible")
        avail_verified = _get_field(train, "availabilityVerified", "availability_verified")
        total_fare = _get_field(train, "totalFare", "fare")

        if (
            train_origin == origin
            and train_dest == destination
            and train_quota == quota
            and is_eligible is True
            and avail_verified is True
            and _is_finite_number(total_fare)
            and total_fare >= 0
        ):
            # Normalise representation for consistent sorting
            normalized_train = dict(train)
            normalized_train["_sort_fare"] = float(total_fare)
            duration = _get_field(train, "durationMinutes", "duration_minutes")
            normalized_train["_sort_duration"] = (
                float(duration) if _is_finite_number(duration) else float("inf")
            )
            normalized_train["_sort_num"] = str(train_num)
            eligible.append(normalized_train)

    # Sort: 1) fare asc, 2) duration asc, 3) train number alphanumeric asc
    def sort_key(t: dict[str, Any]):
        num_str = t["_sort_num"]
        # If numeric, sort by int value; otherwise sort as string
        num_val = int(num_str) if num_str.isdigit() else num_str
        return (t["_sort_fare"], t["_sort_duration"], num_val)

    eligible.sort(key=sort_key)

    # Clean up internal sort keys
    ranked: list[dict[str, Any]] = []
    for t in eligible:
        item = {k: v for k, v in t.items() if not k.startswith("_sort_")}
        ranked.append(item)

    selected = ranked[0] if ranked else None
    status = "OPTIONS_FOUND" if ranked else "NO_VERIFIED_OPTIONS"

    return {
        "selected": selected,
        "ranked": ranked,
        "status": status,
    }
