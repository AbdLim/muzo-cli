"""HTTP client for the Radio Browser API."""

import logging
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from muzo import __version__
from muzo.radio.models import Station

logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS: tuple[str, ...] = (
    "https://de1.api.radio-browser.info",
    "https://de2.api.radio-browser.info",
    "https://fi1.api.radio-browser.info",
    "https://at1.api.radio-browser.info",
)
DEFAULT_BASE_URL = DEFAULT_BASE_URLS[0]
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
        base_url: str | Sequence[str] = DEFAULT_BASE_URLS,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        urls = [base_url] if isinstance(base_url, str) else list(base_url)
        self._base_urls = [u.rstrip("/") for u in urls if u.strip()]
        if not self._base_urls:
            raise ValueError("At least one radio directory base URL is required.")
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
        params = {
            "tag": tag,
            "hidebroken": "true",
            "limit": str(limit),
            "order": "clickcount",
            "reverse": "true",
        }

        response = await self._get("/json/stations/search", params=params)

        try:
            payload = response.json()
        except Exception as err:
            raise RadioResponseError(
                f"Malformed JSON response from radio directory: {err}"
            ) from err

        if not isinstance(payload, list):
            raise RadioResponseError("Expected list of stations from radio directory.")

        return self._parse_stations(payload)

    async def get_station(self, station_id: str) -> Station | None:
        """Look up a single station by its Radio Browser UUID.

        Returns None if the directory has no valid station with that id.
        """
        clean_id = station_id.strip()
        if not clean_id:
            return None
        response = await self._get(f"/json/stations/byuuid/{quote(clean_id, safe='')}")
        try:
            payload = response.json()
        except Exception as err:
            raise RadioResponseError(
                f"Malformed JSON response from radio directory: {err}"
            ) from err
        if not isinstance(payload, list):
            raise RadioResponseError("Expected list of stations from radio directory.")
        stations = self._parse_stations(payload)
        return stations[0] if stations else None

    async def _get(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        """GET a path, falling back through the configured mirrors on failure.

        Network errors, timeouts and HTTP 5xx move on to the next mirror; the mirror that
        last succeeded is tried first next time. Other HTTP errors (e.g. 4xx) are not retried.
        """
        last_error: RadioError | None = None
        for base in list(self._base_urls):
            try:
                response = await self._client.get(f"{base}{path}", params=params)
                response.raise_for_status()
            except httpx.TimeoutException as err:
                last_error = RadioNetworkError(f"Connection to radio directory timed out: {err}")
                last_error.__cause__ = err
                logger.debug("Mirror %s timed out: %s", base, err)
                continue
            except httpx.NetworkError as err:
                last_error = RadioNetworkError(
                    f"Network error connecting to radio directory: {err}"
                )
                last_error.__cause__ = err
                logger.debug("Mirror %s unreachable: %s", base, err)
                continue
            except httpx.HTTPStatusError as err:
                status = err.response.status_code
                last_error = RadioResponseError(f"Radio directory returned HTTP {status}")
                last_error.__cause__ = err
                if status >= 500:
                    logger.debug("Mirror %s returned HTTP %s", base, status)
                    continue
                raise last_error from err

            if base != self._base_urls[0]:
                self._base_urls.remove(base)
                self._base_urls.insert(0, base)
            return response

        assert last_error is not None
        raise last_error

    async def record_click(self, station_id: str) -> None:
        """Notify the directory of a station play event (fire-and-forget)."""
        if not station_id or not station_id.strip():
            return
        try:
            await self._get(f"/json/url/{station_id.strip()}")
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
