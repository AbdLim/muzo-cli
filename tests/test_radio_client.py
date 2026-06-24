"""Tests for the Radio Browser API client."""

import httpx
import pytest

from muzo.radio.client import RadioBrowserClient, RadioNetworkError, RadioResponseError


@pytest.mark.asyncio
async def test_search_stations_success():
    """RadioBrowserClient parses valid station payload and honors resolved URL."""
    sample_json = [
        {
            "stationuuid": "uuid-1",
            "name": "Lofi Chill Radio",
            "url": "http://stream.example.com/live",
            "url_resolved": "https://resolved.example.com/stream",
            "tags": "lofi,chill,beats",
            "codec": "MP3",
            "bitrate": 128,
            "homepage": "https://example.com",
        },
        {
            # Falls back to url when url_resolved is empty
            "stationuuid": "uuid-2",
            "name": "Ambient Space",
            "url": "https://stream2.example.com/ambient",
            "url_resolved": "",
            "tags": "ambient,space",
            "codec": "AAC",
            "bitrate": 192,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/json/stations/search"
        assert request.url.params["tag"] == "lofi"
        assert request.url.params["hidebroken"] == "true"
        return httpx.Response(200, json=sample_json)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = RadioBrowserClient("https://mock.api", client=http_client)
        stations = await client.search_stations(tag="lofi", limit=10)

        assert len(stations) == 2
        assert stations[0].id == "uuid-1"
        assert stations[0].name == "Lofi Chill Radio"
        assert stations[0].stream_url == "https://resolved.example.com/stream"
        assert stations[0].codec == "MP3"
        assert stations[0].bitrate_kbps == 128
        assert stations[0].tags == ("lofi", "chill", "beats")
        assert stations[0].homepage == "https://example.com"

        assert stations[1].id == "uuid-2"
        assert stations[1].stream_url == "https://stream2.example.com/ambient"


@pytest.mark.asyncio
async def test_search_stations_filters_invalid_and_unsafe_entries():
    """Client skips rows with missing IDs, names, or non-http URLs, and strips ANSI escapes."""
    sample_json = [
        {
            # Missing name
            "stationuuid": "uuid-no-name",
            "url": "http://example.com/stream",
        },
        {
            # Non-http scheme
            "stationuuid": "uuid-bad-scheme",
            "name": "Dangerous Station",
            "url": "file:///etc/passwd",
        },
        {
            # Control / ANSI characters in name
            "stationuuid": "uuid-ansi",
            "name": "\x1b[31mRed\x1b[0m Alert \x00Radio",
            "url": "https://example.com/safe",
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sample_json)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = RadioBrowserClient("https://mock.api", client=http_client)
        stations = await client.search_stations(tag="all")

        assert len(stations) == 1
        assert stations[0].id == "uuid-ansi"
        assert stations[0].name == "Red Alert Radio"


@pytest.mark.asyncio
async def test_search_stations_http_errors():
    """Client raises RadioResponseError on 4xx/5xx or malformed JSON."""

    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(error_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = RadioBrowserClient("https://mock.api", client=http_client)
        with pytest.raises(RadioResponseError, match="HTTP 500"):
            await client.search_stations(tag="lofi")


@pytest.mark.asyncio
async def test_search_stations_timeout():
    """Client raises RadioNetworkError on connection timeouts."""

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Network timed out")

    transport = httpx.MockTransport(timeout_handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = RadioBrowserClient("https://mock.api", client=http_client)
        with pytest.raises(RadioNetworkError, match="timed out"):
            await client.search_stations(tag="lofi")


@pytest.mark.asyncio
async def test_record_click():
    """record_click hits the click endpoint and suppresses failures cleanly."""
    recorded = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/json/url/"):
            recorded.append(request.url.path)
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = RadioBrowserClient("https://mock.api", client=http_client)
        await client.record_click("uuid-123")
        assert recorded == ["/json/url/uuid-123"]
