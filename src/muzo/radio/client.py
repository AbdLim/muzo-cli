"""HTTP client for the Radio Browser API."""

import logging
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

import httpx

from muzo import __version__
from muzo.radio.models import Station

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://de1.api.radio-browser.info"
DEFAULT_USER_AGENT = f"muzo/{__version__} (terminal ambient radio)"
DEFAULT_TIMEOUT = httpx.Timeout(timeout=10.0, connect=5.0)

_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def sanitize_text(text: str) -> str:
    """Strip ANSI escape sequences and control characters from untrusted strings."""
    without_ansi = _ANSI_ESCAPE_PATTERN.sub("", text)
    without_controls = _CONTROL_CHARS_PATTERN.sub("", without_ansi)
    return without_controls.strip()


class RadioError(Exception):
    """Base exception for radio service operations."""


class RadioNetworkError(RadioError):
    """Raised when network connectivity or DNS resolution fails."""


class RadioResponseError(RadioError):
    """Raised when the API returns an HTTP error or malformed payload."""


class RadioBrowserClient:
    """Asynchronous client for querying the Radio Browser directory."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client session."""
        if not self._external_client:
            await self._client.aclose()

    async def __aenter__(self) -> "RadioBrowserClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def search_stations(
        self,
        *,
        tag: str,
        limit: int = 20,
    ) -> list[Station]:
        """Search for stations by tag, ordered by popularity.

        Args:
            tag: Search tag (e.g. 'lofi', 'ambient').
            limit: Maximum results to retrieve.

        Returns:
            List of validated Station objects.

        Raises:
            RadioNetworkError: If connection or timeout occurs.
            RadioResponseError: If the server returns an error or invalid payload.
        """
        endpoint = f"{self._base_url}/json/stations/search"
        params = {
            "tag": tag,
            "hidebroken": "true",
            "limit": str(limit),
            "order": "clickcount",
            "reverse": "true",
        }

        try:
            response = await self._client.get(endpoint, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as err:
            raise RadioNetworkError(f"Connection to radio directory timed out: {err}") from err
        except httpx.NetworkError as err:
            raise RadioNetworkError(f"Network error connecting to radio directory: {err}") from err
        except httpx.HTTPStatusError as err:
            raise RadioResponseError(
                f"Radio directory returned HTTP {err.response.status_code}"
            ) from err

        try:
            payload = response.json()
        except Exception as err:
            raise RadioResponseError(
                f"Malformed JSON response from radio directory: {err}"
            ) from err

        if not isinstance(payload, list):
            raise RadioResponseError("Expected list of stations from radio directory.")

        return self._parse_stations(payload)

    async def record_click(self, station_id: str) -> None:
        """Notify the directory of a station play event (fire-and-forget)."""
        if not station_id or not station_id.strip():
            return
        endpoint = f"{self._base_url}/json/url/{station_id.strip()}"
        try:
            await self._client.get(endpoint)
        except Exception as err:
            logger.debug("Failed to record station click for %s: %s", station_id, err)

    def _parse_stations(self, raw_stations: Sequence[Any]) -> list[Station]:
        """Defensively parse raw API station records into typed Station objects."""
        stations: list[Station] = []

        for item in raw_stations:
            if not isinstance(item, dict):
                continue

            station_id = item.get("stationuuid")
            name = item.get("name")
            if not station_id or not isinstance(station_id, str):
                continue
            if not name or not isinstance(name, str):
                continue

            # Prefer resolved URL over initial URL
            raw_url = item.get("url_resolved") or item.get("url")
            if not raw_url or not isinstance(raw_url, str):
                continue

            parsed_url = urlparse(raw_url.strip())
            if parsed_url.scheme.lower() not in ("http", "https") or not parsed_url.netloc:
                continue

            clean_name = sanitize_text(name)
            if not clean_name:
                continue

            raw_tags = item.get("tags", "")
            tags: tuple[str, ...] = ()
            if isinstance(raw_tags, str) and raw_tags:
                tags = tuple(
                    clean_tag
                    for t in raw_tags.split(",")
                    if (clean_tag := sanitize_text(t).lower())
                )

            codec = sanitize_text(item["codec"]) if isinstance(item.get("codec"), str) else None
            bitrate_raw = item.get("bitrate")
            bitrate: int | None = None
            if isinstance(bitrate_raw, int) and bitrate_raw > 0:
                bitrate = bitrate_raw

            homepage_raw = item.get("homepage")
            homepage: str | None = None
            if isinstance(homepage_raw, str) and homepage_raw.strip():
                hp_parsed = urlparse(homepage_raw.strip())
                if hp_parsed.scheme.lower() in ("http", "https"):
                    homepage = homepage_raw.strip()

            stations.append(
                Station(
                    id=station_id.strip(),
                    name=clean_name,
                    stream_url=raw_url.strip(),
                    tags=tags,
                    codec=codec if codec else None,
                    bitrate_kbps=bitrate,
                    homepage=homepage,
                )
            )

        return stations
