"""Tests for PlayerController state coordination."""

from typing import Any

import pytest

from muzo.player.controller import PlayerController
from muzo.player.engine import MpvEngine
from muzo.player.models import (
    MpvNotInstalledError,
    PlaybackState,
    PlaybackStatus,
)
from muzo.radio.models import Station


class FakeMpvEngine(MpvEngine):
    """Test fake for MpvEngine that tracks issued commands without subprocesses."""

    def __init__(self) -> None:
        super().__init__()
        self.commands_sent: list[list[Any]] = []
        self.should_fail_load = False
        self.simulate_missing = False

    async def start(self) -> None:
        if self.simulate_missing:
            raise MpvNotInstalledError("Simulated missing mpv")

    async def loadfile(self, stream_url: str) -> None:
        if self.simulate_missing:
            raise MpvNotInstalledError("Simulated missing mpv")
        if self.should_fail_load:
            raise RuntimeError("Stream load failed")
        self.commands_sent.append(["loadfile", stream_url])

    async def pause(self) -> None:
        self.commands_sent.append(["pause"])

    async def resume(self) -> None:
        self.commands_sent.append(["resume"])

    async def stop(self) -> None:
        self.commands_sent.append(["stop"])

    async def set_volume(self, volume: int) -> None:
        self.commands_sent.append(["volume", volume])

    async def close(self) -> None:
        self.commands_sent.append(["close"])


@pytest.mark.asyncio
async def test_controller_play_station_flow():
    """Selecting a station transitions to CONNECTING, then to PLAYING on file-loaded."""
    engine = FakeMpvEngine()

    controller = PlayerController(engine=engine)
    states: list[PlaybackState] = []
    controller.add_listener(lambda s: states.append(s))

    station = Station(id="st-1", name="Lo-Fi Beats", stream_url="https://lofi.stream")
    await controller.play_station(station)

    assert controller.state.status == PlaybackStatus.CONNECTING
    assert controller.state.station == station
    assert engine.commands_sent == [["loadfile", "https://lofi.stream"]]

    # Emit file-loaded event from engine
    controller._handle_mpv_event("file-loaded", {})
    assert controller.state.status == PlaybackStatus.PLAYING
    assert controller.state.error_message is None


@pytest.mark.asyncio
async def test_controller_toggle_pause():
    """Toggle pause alternates between PLAYING and PAUSED."""
    engine = FakeMpvEngine()
    controller = PlayerController(engine=engine)
    station = Station(id="st-1", name="Lo-Fi Beats", stream_url="https://lofi.stream")

    await controller.play_station(station)
    controller._handle_mpv_event("file-loaded", {})
    assert controller.state.status == PlaybackStatus.PLAYING

    await controller.toggle_pause()
    assert controller.state.status == PlaybackStatus.PAUSED

    await controller.toggle_pause()
    assert controller.state.status == PlaybackStatus.PLAYING


@pytest.mark.asyncio
async def test_controller_volume_clamping():
    """Volume adjusts within [0, 100] bounds."""
    engine = FakeMpvEngine()
    controller = PlayerController(engine=engine, initial_volume=70)

    await controller.change_volume(10)
    assert controller.state.volume == 80

    await controller.change_volume(50)
    assert controller.state.volume == 100

    await controller.change_volume(-150)
    assert controller.state.volume == 0


@pytest.mark.asyncio
async def test_controller_stream_error_event():
    """end-file with reason 'error' transitions to ERROR state."""
    engine = FakeMpvEngine()
    controller = PlayerController(engine=engine)
    station = Station(id="st-1", name="Lo-Fi Beats", stream_url="https://lofi.stream")

    await controller.play_station(station)
    controller._handle_mpv_event("end-file", {"reason": "error"})

    assert controller.state.status == PlaybackStatus.ERROR
    assert controller.state.error_message is not None


@pytest.mark.asyncio
async def test_controller_missing_mpv():
    """When mpv is missing, transitions to ERROR with installation instructions."""
    engine = FakeMpvEngine()

    engine.simulate_missing = True
    controller = PlayerController(engine=engine)

    station = Station(id="st-1", name="Lo-Fi Beats", stream_url="https://lofi.stream")
    await controller.play_station(station)

    assert controller.state.status == PlaybackStatus.ERROR
    assert "mpv" in (controller.state.error_message or "")
