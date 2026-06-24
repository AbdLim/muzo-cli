"""Mood categories and associated search tags for discovering radio stations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Mood:
    """A curated mood category with query tags for Radio Browser search."""

    name: str
    tags: tuple[str, ...]


DEFAULT_MOODS: tuple[Mood, ...] = (
    Mood(name="Lofi & Chill", tags=("lofi", "chillhop", "downtempo")),
    Mood(name="Deep Focus", tags=("ambient", "minimal", "drone")),
    Mood(name="Late Night Jazz", tags=("jazz", "smooth jazz")),
    Mood(name="Electronic", tags=("synthwave", "electronic", "downtempo")),
)
