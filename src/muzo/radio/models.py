"""Radio station models and navigational coordinates for the airwaves."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Station:
    """Audio stream metadata for an internet radio station."""

    id: str
    name: str
    stream_url: str
    tags: tuple[str, ...] = ()
    codec: str | None = None
