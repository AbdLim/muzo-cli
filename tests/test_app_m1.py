"""Integration tests for Muzo interactive radio streaming and controls."""

import pytest
from textual.geometry import Size

from muzo.app import MuzoApp
from muzo.player.controller import PlayerController
from muzo.player.engine import MpvEngine
from muzo.player.models import PlaybackStatus
from muzo.radio.client import RadioBrowserClient
from muzo.radio.models import Station
from muzo.radio.service import RadioService
from muzo.ui.screens.station_picker import StationPickerScreen
from muzo.ui.widgets.player_status import PlayerStatusWidget
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
                id="test-station-1",
                name="Chillhop Beats",
                stream_url="https://chill.test/stream",
                codec="MP3",
                bitrate_kbps=128,
            ),
            Station(
                id="test-station-2",
                name="Nightwave Plaza",
                stream_url="https://nightwave.test/stream",
                codec="AAC",
                bitrate_kbps=192,
            ),
        ]

    async def record_click(self, station_id: str) -> None:
        pass

    async def aclose(self) -> None:
        pass


@pytest.mark.asyncio
async def test_app_default_scene_is_rainy_window():
    """App mounts with rainy-window scene as default."""
    app = MuzoApp()
    async with app.run_test(size=(80, 24)) as pilot:
        scene_view = pilot.app.query_one(SceneView)
        assert scene_view.scene is not None
        assert scene_view.scene.id == "rainy-window"


@pytest.mark.asyncio
async def test_open_and_dismiss_station_picker():
    """Pressing 'r' opens the station picker and Escape dismisses it."""
    client = MockRadioClient()
    radio_service = RadioService(client=client)
    app = MuzoApp(radio_service=radio_service)

    async with app.run_test(size=(80, 24)) as pilot:
        assert not isinstance(pilot.app.screen, StationPickerScreen)

        # Press 'r' to open picker
        await pilot.press("r")
        assert isinstance(pilot.app.screen, StationPickerScreen)

        # Press Escape to dismiss
        await pilot.press("escape")
        assert not isinstance(pilot.app.screen, StationPickerScreen)


@pytest.mark.asyncio
async def test_select_station_and_playback_controls():
    """User can select a station from picker, hear audio, pause, adjust volume, and stop."""
    client = MockRadioClient()
    radio_service = RadioService(client=client)
    engine = MockEngine()
    controller = PlayerController(engine=engine, initial_volume=70)
    app = MuzoApp(controller=controller, radio_service=radio_service)

    async with app.run_test(size=(80, 24)) as pilot:
        # Open station picker
        await pilot.press("r")
        assert isinstance(pilot.app.screen, StationPickerScreen)

        # Allow worker task to fetch mock stations and populate list
        await pilot.pause(0.1)

        # Select first station by pressing Enter
        await pilot.press("enter")
        assert not isinstance(pilot.app.screen, StationPickerScreen)

        # Controller should now be connecting
        assert controller.state.status == PlaybackStatus.CONNECTING
        assert controller.state.station is not None
        assert controller.state.station.name == "Chillhop Beats"
        assert "loadfile:https://chill.test/stream" in engine.commands

        # Simulate mpv file-loaded confirmation event
        controller._handle_mpv_event("file-loaded", {})
        assert controller.state.status == PlaybackStatus.PLAYING

        # Check PlayerStatusWidget reflects playing state
        status_widget = pilot.app.query_one(PlayerStatusWidget)
        assert "Playing" in status_widget._left_static.render_line(0).text

        # Test Space key pauses stream
        await pilot.press("space")
        assert controller.state.status == PlaybackStatus.PAUSED
        assert "pause" in engine.commands

        # Test Space key resumes stream
        await pilot.press("space")
        assert controller.state.status == PlaybackStatus.PLAYING
        assert "resume" in engine.commands

        # Test volume controls (+/-)
        await pilot.press("plus")
        assert controller.state.volume == 75
        await pilot.press("minus")
        assert controller.state.volume == 70

        # Test stop key (x)
        await pilot.press("x")
        assert controller.state.status == PlaybackStatus.STOPPED
        assert "stop" in engine.commands


@pytest.mark.asyncio
async def test_app_resize_narrow():
    """App handles resizing to compact 40x12 without errors."""
    app = MuzoApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.resize_terminal(40, 12)
        assert pilot.app.size == Size(40, 12)
        scene_view = pilot.app.query_one(SceneView)
        assert scene_view is not None


async def _make_app(config=None, stations=None):
    engine = MockEngine()
    controller = PlayerController(engine=engine)
    service = RadioService(client=MockRadioClient())
    app = MuzoApp(config=config, controller=controller, radio_service=service)
    return app, engine


@pytest.mark.asyncio
async def test_start_hint_visible_until_station_chosen():
    app, _ = await _make_app()
    async with app.run_test() as pilot:
        hint = app.query_one("#start-hint")
        assert hint.display is True
        app.controller.preload_station(
            Station(id="s", name="S", stream_url="https://s.test/stream")
        )
        await pilot.pause()
        assert hint.display is False


@pytest.mark.asyncio
async def test_selecting_station_remembers_it(isolated_default_config):
    from muzo.config import load_config

    app, engine = await _make_app()
    async with app.run_test() as pilot:
        station = Station(id="test-station-1", name="Chillhop Beats", stream_url="https://c.test/s")
        app._on_station_selected(station)
        await pilot.pause()
        assert app.config.station == "test-station-1"
    assert load_config(isolated_default_config, explicit=True).station == "test-station-1"


@pytest.mark.asyncio
async def test_last_station_is_preloaded_not_autoplayed():
    from muzo.config import AppConfig

    class LookupClient(MockRadioClient):
        async def get_station(self, station_id):
            return Station(id=station_id, name="Remembered FM", stream_url="https://r.test/s")

    engine = MockEngine()
    app = MuzoApp(
        config=AppConfig(station="abc"),
        controller=PlayerController(engine=engine),
        radio_service=RadioService(client=LookupClient()),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        state = app.controller.state
        assert state.station is not None and state.station.name == "Remembered FM"
        assert state.status == PlaybackStatus.STOPPED
        assert engine.commands == []

        await pilot.press("space")
        await pilot.pause()
        assert engine.commands == ["loadfile:https://r.test/s"]


@pytest.mark.asyncio
async def test_autoplay_starts_last_station():
    from muzo.config import AppConfig

    class LookupClient(MockRadioClient):
        async def get_station(self, station_id):
            return Station(id=station_id, name="Remembered FM", stream_url="https://r.test/s")

    engine = MockEngine()
    app = MuzoApp(
        config=AppConfig(station="abc", autoplay=True),
        controller=PlayerController(engine=engine),
        radio_service=RadioService(client=LookupClient()),
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        assert engine.commands == ["loadfile:https://r.test/s"]
