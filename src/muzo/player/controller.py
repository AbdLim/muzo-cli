"""High-level audio playback coordinator and state manager."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from muzo.player.engine import MpvEngine
from muzo.player.models import (
    MpvNotInstalledError,
    PlaybackState,
    PlaybackStatus,
    PlayerError,
)
from muzo.radio.models import Station

logger = logging.getLogger(__name__)

StateListener = Callable[[PlaybackState], None]


class PlayerController:
    """Manages audio player state transitions and translates user intents to engine actions."""

    def __init__(
        self,
        engine: MpvEngine | None = None,
        initial_volume: int = 70,
        click_recorder: Callable[[str], Any] | None = None,
    ) -> None:
        self._initial_volume = max(0, min(100, initial_volume))
        self._click_recorder = click_recorder
        self._listeners: list[StateListener] = []

        self._state = PlaybackState(
            status=PlaybackStatus.STOPPED,
            station=None,
            volume=self._initial_volume,
            error_message=None,
        )

        self._engine = engine or MpvEngine(
            volume=self._initial_volume,
            event_callback=self._handle_mpv_event,
        )

        self._current_request_id = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> PlaybackState:
        """Current immutable playback state snapshot."""
        return self._state

    @property
    def engine(self) -> MpvEngine:
        """The underlying low-level mpv engine."""
        return self._engine

    def add_listener(self, listener: StateListener) -> None:
        """Subscribe to playback state transitions."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: StateListener) -> None:
        """Unsubscribe from state transitions."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _update_state(
        self,
        *,
        status: PlaybackStatus | None = None,
        station: Station | None = ...,  # type: ignore[assignment]
        volume: int | None = None,
        error_message: str | None = ...,  # type: ignore[assignment]
    ) -> None:
        """Atomically update state snapshot and notify subscribers."""
        new_status = status if status is not None else self._state.status
        new_station = station if station is not ... else self._state.station
        new_volume = volume if volume is not None else self._state.volume
        new_error = error_message if error_message is not ... else self._state.error_message

        self._state = PlaybackState(
            status=new_status,
            station=new_station,
            volume=new_volume,
            error_message=new_error,
        )

        for listener in list(self._listeners):
            try:
                listener(self._state)
            except Exception as exc:
                logger.error("Error in state listener: %s", exc)

    def _handle_mpv_event(self, event_name: str, event_data: dict[str, Any]) -> None:
        """Process incoming asynchronous mpv IPC events."""
        if event_name == "file-loaded":
            if self._state.status in (PlaybackStatus.CONNECTING, PlaybackStatus.BUFFERING):
                self._update_state(status=PlaybackStatus.PLAYING, error_message=None)

        elif event_name == "end-file":
            reason = event_data.get("reason")
            if reason == "error":
                self._update_state(
                    status=PlaybackStatus.ERROR,
                    error_message="Stream connection failed or unsupported format.",
                )
            elif reason in ("eof", "stop"):
                if self._state.status != PlaybackStatus.ERROR:
                    self._update_state(status=PlaybackStatus.STOPPED)

        elif event_name == "property-change":
            prop_name = event_data.get("name")
            prop_val = event_data.get("data")
            if prop_name == "pause" and isinstance(prop_val, bool):
                if prop_val and self._state.status == PlaybackStatus.PLAYING:
                    self._update_state(status=PlaybackStatus.PAUSED)
                elif not prop_val and self._state.status == PlaybackStatus.PAUSED:
                    self._update_state(status=PlaybackStatus.PLAYING)
            elif prop_name == "volume" and isinstance(prop_val, (int, float)):
                self._update_state(volume=int(prop_val))

    async def play_station(self, station: Station) -> None:
        """Switch audio playback to the specified station."""
        async with self._lock:
            self._current_request_id += 1
            request_token = self._current_request_id

            self._update_state(
                status=PlaybackStatus.CONNECTING,
                station=station,
                error_message=None,
            )

        # Trigger click count recording (fire and forget)
        if self._click_recorder:
            try:
                res = self._click_recorder(station.id)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

        try:
            await self._engine.loadfile(station.stream_url)
        except MpvNotInstalledError as err:
            if request_token == self._current_request_id:
                self._update_state(
                    status=PlaybackStatus.ERROR,
                    error_message=str(err),
                )
        except PlayerError as err:
            if request_token == self._current_request_id:
                self._update_state(
                    status=PlaybackStatus.ERROR,
                    error_message=f"Playback error: {err}",
                )
        except Exception as err:
            if request_token == self._current_request_id:
                self._update_state(
                    status=PlaybackStatus.ERROR,
                    error_message=f"Unexpected error: {err}",
                )

    async def toggle_pause(self) -> None:
        """Toggle playback pause / resume."""
        if self._state.status == PlaybackStatus.PLAYING:
            try:
                await self._engine.pause()
                self._update_state(status=PlaybackStatus.PAUSED)
            except Exception as err:
                logger.error("Failed to pause playback: %s", err)
        elif self._state.status == PlaybackStatus.PAUSED:
            try:
                await self._engine.resume()
                self._update_state(status=PlaybackStatus.PLAYING)
            except Exception as err:
                logger.error("Failed to resume playback: %s", err)

    async def stop(self) -> None:
        """Stop audio playback."""
        try:
            await self._engine.stop()
        except Exception as err:
            logger.debug("Error while stopping player: %s", err)
        self._update_state(status=PlaybackStatus.STOPPED)

    async def set_volume(self, volume: int) -> None:
        """Set volume percentage between 0 and 100."""
        clamped = max(0, min(100, volume))
        self._update_state(volume=clamped)
        try:
            await self._engine.set_volume(clamped)
        except Exception as err:
            logger.debug("Error setting volume: %s", err)

    async def change_volume(self, delta: int) -> None:
        """Adjust volume by the given delta."""
        await self.set_volume(self._state.volume + delta)

    async def close(self) -> None:
        """Tear down engine and clean up."""
        try:
            await self._engine.close()
        except Exception as err:
            logger.debug("Error closing engine: %s", err)
        self._update_state(status=PlaybackStatus.STOPPED)
