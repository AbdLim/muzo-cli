"""Tests for RadioService."""

import pytest

from muzo.radio.client import RadioBrowserClient
from muzo.radio.models import Station
from muzo.radio.service import RadioService


class FakeRadioClient(RadioBrowserClient):
    """Fake client returning predetermined stations without network calls."""

    def __init__(self, responses: dict[str, list[Station]]) -> None:
        self.responses = responses
        self.call_counts: dict[str, int] = {}
        self.recorded_clicks: list[str] = []

    async def search_stations(self, *, tag: str, limit: int = 20) -> list[Station]:
        self.call_counts[tag] = self.call_counts.get(tag, 0) + 1
        return self.responses.get(tag, [])

    async def record_click(self, station_id: str) -> None:
        self.recorded_clicks.append(station_id)

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_radio_service_deduplicates_across_tags():
    """RadioService merges multiple tags for a mood and deduplicates by station ID."""
    s1 = Station(id="s1", name="Chill One", stream_url="https://s1.test")
    s2 = Station(id="s2", name="Chill Two", stream_url="https://s2.test")
    s3 = Station(id="s1", name="Chill One Duplicate", stream_url="https://s1.test")

    client = FakeRadioClient(
        {
            "lofi": [s1, s2],
            "chillhop": [s3],
            "downtempo": [],
        }
    )
    service = RadioService(client=client)

    results = await service.search_mood("Lofi & Chill", limit=10)
    assert len(results) == 2
    assert [s.id for s in results] == ["s1", "s2"]


@pytest.mark.asyncio
async def test_radio_service_cache_avoids_repeated_requests():
    """RadioService caches results within TTL."""
    s1 = Station(id="s1", name="Focus One", stream_url="https://s1.test")
    client = FakeRadioClient({"ambient": [s1], "minimal": [], "drone": []})
    service = RadioService(client=client, cache_ttl_seconds=60.0)

    res1 = await service.search_mood("Deep Focus")
    res2 = await service.search_mood("Deep Focus")

    assert res1 == res2
    # Client should only have been called once for the first tag
    assert client.call_counts["ambient"] == 1
