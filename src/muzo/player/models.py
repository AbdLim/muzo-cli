"""Data models, status enumeration, and exceptions for the audio player."""

from dataclasses import dataclass
from enum import StrEnum

from muzo.radio.models import Station


class PlaybackStatus(StrEnum):
    """Current playback engine state."""

    STOPPED = "stopped"
    CONNECTING = "connecting"
    BUFFERING = "buffering"
    PLAYING = "playing"
    PAUSED = "paused"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PlaybackState:
    """Snapshot of player status, active station, volume, and optional error message."""

    status: PlaybackStatus = PlaybackStatus.STOPPED
    station: Station | None = None
    volume: int = 70
    error_message: str | None = None


class PlayerError(Exception):
    """Base exception for audio player operations."""


class MpvNotInstalledError(PlayerError):
    """Raised when the mpv executable cannot be found on PATH."""


class MpvStartupError(PlayerError):
    """Raised when the mpv process or IPC socket fails to initialize."""


class MpvIPCError(PlayerError):
    """Raised when IPC communication with mpv encounters an error."""


class StreamFailureError(PlayerError):
    """Raised when an audio stream cannot be opened or played."""
