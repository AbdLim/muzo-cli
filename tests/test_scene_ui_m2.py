"""UI integration tests for M2 scene picker, scene switching, and focus mode."""

import pytest
from textual.geometry import Size
from textual.widgets import Label

from muzo.app import MuzoApp
from muzo.config import AppConfig
from muzo.player.controller import PlayerController
from muzo.player.engine import MpvEngine
from muzo.radio.client import RadioBrowserClient
from muzo.radio.models import Station
from muzo.radio.service import RadioService
from muzo.scenes.registry import create_default_registry
from muzo.ui.screens.scene_picker import ScenePickerScreen
from muzo.ui.widgets.scene_view import SceneView


class MockEngine(MpvEngine):
    """Mock mpv engine recording commands without subprocesses."""

    def __init__(self) -> None:
        super().__init__()
        self.commands: list[str] = []

    async def start(self) -> None:
        pass

    async def loadfile(self, stream_url: str) -> None:
        self.commands.append(f"loadfile:{stream_url}")

    async def pause(self) -> None:
        self.commands.append("pause")

    async def resume(self) -> None:
        self.commands.append("resume")

    async def stop(self) -> None:
        self.commands.append("stop")

    async def set_volume(self, volume: int) -> None:
        self.commands.append(f"volume:{volume}")

    async def close(self) -> None:
        self.commands.append("close")


class MockRadioClient(RadioBrowserClient):
    """Mock radio client returning test stations."""

    async def search_stations(self, *, tag: str, limit: int = 20) -> list[Station]:
        return [
            Station(
                id="station-lofi-1",
                name="Lofi Cafe",
                stream_url="https://lofi.test/stream",
                codec="MP3",
                bitrate_kbps=128,
            )
        ]


@pytest.mark.asyncio
async def test_scene_picker_open_and_switch():
    """Pressing 's' opens scene picker, and selecting a scene switches without touching audio."""
    mock_engine = MockEngine()
    controller = PlayerController(engine=mock_engine)
    radio_service = RadioService(client=MockRadioClient())
    registry = create_default_registry()
    app = MuzoApp(
        config=AppConfig(scene="rainy-window"),
        registry=registry,
        controller=controller,
        radio_service=radio_service,
    )

    async with app.run_test(size=Size(80, 24)) as pilot:
        assert app._active_scene.id == "rainy-window"

        # Record initial audio commands
        audio_commands_before = list(mock_engine.commands)

        # Press 's' to open ScenePickerScreen
        await pilot.press("s")
        assert isinstance(app.screen, ScenePickerScreen)

        # Navigate down and press enter to pick horizon
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause(0.3)

        # Modal closed, active scene switched
        assert not isinstance(app.screen, ScenePickerScreen)
        assert app._active_scene.id == "horizon"

        # Scene view widget updated
        scene_view = app.query_one(SceneView)
        assert scene_view.scene is not None
        assert scene_view.scene.id == "horizon"

        # Header title updated
        header_status = app.query_one("#header-status", Label)
        assert "Horizon" in str(header_status.render())

        # Crucial: Player controller was not interrupted or altered
        assert mock_engine.commands == audio_commands_before


@pytest.mark.asyncio
async def test_focus_mode_toggle():
    """Pressing 'f' toggles .focus-mode class without interrupting audio."""
    mock_engine = MockEngine()
    controller = PlayerController(engine=mock_engine)
    radio_service = RadioService(client=MockRadioClient())
    registry = create_default_registry()
    app = MuzoApp(
        config=AppConfig(scene="rainy-window", focus_mode=False),
        registry=registry,
        controller=controller,
        radio_service=radio_service,
    )

    async with app.run_test(size=Size(80, 24)) as pilot:
        assert not app.has_class("focus-mode")

        audio_commands_before = list(mock_engine.commands)

        # Toggle on focus mode
        await pilot.press("f")
        assert app.has_class("focus-mode")
        assert app._is_focus_mode is True

        # Toggle off focus mode
        await pilot.press("f")
        assert not app.has_class("focus-mode")
        assert app._is_focus_mode is False

        # Audio commands unchanged
        assert mock_engine.commands == audio_commands_before


@pytest.mark.asyncio
async def test_scene_picker_dismiss_with_escape():
    """Pressing Escape inside scene picker dismisses without changing active scene."""
    mock_engine = MockEngine()
    controller = PlayerController(engine=mock_engine)
    radio_service = RadioService(client=MockRadioClient())
    registry = create_default_registry()
    app = MuzoApp(
        config=AppConfig(scene="rainy-window"),
        registry=registry,
        controller=controller,
        radio_service=radio_service,
    )

    async with app.run_test(size=Size(80, 24)) as pilot:
        await pilot.press("s")
        assert isinstance(app.screen, ScenePickerScreen)

        # Dismiss with Escape
        await pilot.press("escape")
        assert not isinstance(app.screen, ScenePickerScreen)
        assert app._active_scene.id == "rainy-window"


@pytest.mark.asyncio
async def test_header_and_picker_display_active_station():
    """Top header and station picker reflect currently playing station."""
    mock_engine = MockEngine()
    controller = PlayerController(engine=mock_engine)
    radio_service = RadioService(client=MockRadioClient())
    registry = create_default_registry()
    app = MuzoApp(
        config=AppConfig(scene="rainy-window"),
        registry=registry,
        controller=controller,
        radio_service=radio_service,
    )

    station = Station(
        id="station-lofi-1",
        name="Lofi Cafe",
        stream_url="https://lofi.test/stream",
        codec="MP3",
        bitrate_kbps=128,
    )

    async with app.run_test(size=Size(80, 24)) as pilot:
        header_station = app.query_one("#header-station", Label)
        assert str(header_station.render()) == ""

        # Play station
        await controller.play_station(station)
        await pilot.pause()

        # Header station label reflects playing station
        assert "Lofi Cafe" in str(header_station.render())

        # Open station picker
        from muzo.ui.screens.station_picker import StationPickerScreen

        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, StationPickerScreen)

        # Now playing banner is displayed in picker
        now_playing = app.screen.query_one("#picker-now-playing")
        assert "Lofi Cafe" in str(now_playing.render())
