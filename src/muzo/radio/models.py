"""Radio station models and metadata for internet audio streams."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Station:
    """Audio stream metadata for an internet radio station."""

    id: str
    name: str
    stream_url: str
    tags: tuple[str, ...] = ()
    codec: str | None = None
    bitrate_kbps: int | None = None
    homepage: str | None = None
