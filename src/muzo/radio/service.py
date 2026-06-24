"""Service layer for searching, deduplicating, and caching radio stations."""

import time

from muzo.radio.client import RadioBrowserClient
from muzo.radio.models import Station
from muzo.radio.moods import DEFAULT_MOODS, Mood


class RadioService:
    """High-level service coordinating station searches across moods."""

    def __init__(
        self,
        client: RadioBrowserClient | None = None,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self._client = client or RadioBrowserClient()
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[float, list[Station]]] = {}

    @property
    def client(self) -> RadioBrowserClient:
        """The underlying API client."""
        return self._client

    async def search_mood(
        self,
        mood: Mood | str,
        limit: int = 20,
    ) -> list[Station]:
        """Search stations for a given mood category, using cached results if fresh."""
        mood_obj = self._resolve_mood(mood)
        cache_key = f"{mood_obj.name}:{limit}"
        now = time.monotonic()

        if cache_key in self._cache:
            cached_time, cached_stations = self._cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_stations

        # Query tags and deduplicate
        seen_ids: set[str] = set()
        collected: list[Station] = []

        for tag in mood_obj.tags:
            stations = await self._client.search_stations(tag=tag, limit=limit)
            for station in stations:
                if station.id not in seen_ids:
                    seen_ids.add(station.id)
                    collected.append(station)
                    if len(collected) >= limit:
                        break
            if len(collected) >= limit:
                break

        self._cache[cache_key] = (now, collected)
        return collected

    async def record_click(self, station_id: str) -> None:
        """Record a play event for the given station."""
        await self._client.record_click(station_id)

    async def aclose(self) -> None:
        """Close the underlying client."""
        await self._client.aclose()

    def _resolve_mood(self, mood: Mood | str) -> Mood:
        """Resolve a Mood instance from either an existing Mood or a string name."""
        if isinstance(mood, Mood):
            return mood
        for m in DEFAULT_MOODS:
            if m.name.lower() == mood.lower():
                return m
        # Fallback to single-tag query if custom string passed
        return Mood(name=mood, tags=(mood.lower(),))
