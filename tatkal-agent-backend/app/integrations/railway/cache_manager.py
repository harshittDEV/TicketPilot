"""
Railway Cache Manager with Freshness Attribution.

Enforces granular TTL freshness windows:
- Station directories: 7 days
- Timetables & Schedules: 24 hours
- Live running status: 2 minutes
- Seat availability: 5 minutes

Distinguishes fresh responses, cached hits, and stale data.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional, Tuple
from app.integrations.railway.contracts import DataFreshnessCategory


class CacheEntry:
    def __init__(self, data: Any, ttl_seconds: float, source: str):
        self.data = data
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.source = source

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class RailwayCacheManager:
    """Thread-safe in-memory cache with freshness metadata."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._evictions: int = 0

    def get(self, key: str, allow_stale: bool = False) -> Optional[Tuple[Any, DataFreshnessCategory]]:
        """
        Retrieve cached value with freshness classification.
        Returns:
            Tuple of (data, DataFreshnessCategory) or None if not found/expired.
        """
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                self._misses += 1
                return None

            if entry.is_expired:
                if allow_stale:
                    self._hits += 1
                    return entry.data, DataFreshnessCategory.STALE
                # Purge expired entry
                del self._store[key]
                self._evictions += 1
                self._misses += 1
                return None

            self._hits += 1
            return entry.data, DataFreshnessCategory.CACHED

    def set(self, key: str, data: Any, ttl_seconds: float, source: str) -> None:
        """Store value with explicit TTL and data source attribution."""
        with self._lock:
            self._store[key] = CacheEntry(data, ttl_seconds, source)

    def invalidate(self, key: str) -> bool:
        """Remove an item from cache."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._store.clear()

    def get_stats(self) -> dict[str, Any]:
        """Return operational metrics for cache."""
        with self._lock:
            # Purge expired on stat inspection
            now = time.time()
            active_keys = [k for k, v in self._store.items() if (now - v.created_at) <= v.ttl_seconds]
            return {
                "active_entries": len(active_keys),
                "total_keys": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_ratio": (
                    round(self._hits / (self._hits + self._misses), 3)
                    if (self._hits + self._misses) > 0
                    else 0.0
                ),
            }


# Singleton cache instance
_cache_instance: Optional[RailwayCacheManager] = None


def get_cache_manager() -> RailwayCacheManager:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RailwayCacheManager()
    return _cache_instance
