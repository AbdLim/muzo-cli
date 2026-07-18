"""Textual application shell for Muzo."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from muzo.config import AppConfig
from muzo.player.controller import PlayerController
from muzo.radio.models import Station
from muzo.radio.service import RadioService
from muzo.scenes.base import Scene
from muzo.scenes.registry import (
    SceneNotFoundError,
    SceneRegistry,
    create_default_registry,
)
from muzo.ui.screens.station_picker import StationPickerScreen
from muzo.ui.widgets.player_status import PlayerStatusWidget
from muzo.ui.widgets.scene_view import SceneView


class HelpScreen(ModalScreen[None]):
    """Modal overlay presenting available keyboard shortcuts and current status."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close Help"),
        Binding("question_mark", "dismiss", "Close Help"),
        Binding("q", "quit_app", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="help-dialog"):
            yield Static(
                "[#7eb6ad][b]muzo — ambient terminal radio[/b][/]\n\n"
                "[b]Shortcuts:[/b]\n"
                "  [#7eb6ad]r[/]        Browse & select radio stations\n"
                "  [#7eb6ad]Space[/]    Toggle pause / resume stream\n"
                "  [#7eb6ad]x[/]        Stop playback\n"
                "  [#7eb6ad]+ / -[/]    Adjust volume by 5%\n"
                "  [#7eb6ad]?[/]        Toggle this help screen\n"
                "  [#7eb6ad]Esc[/]      Dismiss dialogs\n"
                "  [#7eb6ad]q[/]        Quit muzo cleanly\n\n"
                "[b]Status:[/b]\n"
                "  Procedural ambient visual scenes with live internet radio.\n"
                "  Requires mpv installed for audio playback.\n\n"
                "[dim]Press Escape or ? to return to the scene[/dim]",
                id="help-content",
            )

    def action_quit_app(self) -> None:
        """Quit the application directly from the help screen."""
        self.app.exit()


class MuzoApp(App[None]):
    """Main Muzo terminal application."""

    CSS_PATH = Path("ui/styles/app.tcss")
    TITLE = "muzo"

    BINDINGS = [
        Binding("q", "quit_app", "Quit", show=False),
        Binding("question_mark", "toggle_help", "Help", show=False),
        Binding("r", "open_station_picker", "Stations", show=False),
        Binding("space", "toggle_pause", "Pause", show=False),
        Binding("x", "stop_audio", "Stop", show=False),
        Binding("plus", "volume_up", "Volume Up", show=False),
        Binding("equals", "volume_up", "Volume Up", show=False),
        Binding("minus", "volume_down", "Volume Down", show=False),
    ]

    def __init__(
        self,
        config: AppConfig | None = None,
        registry: SceneRegistry | None = None,
        controller: PlayerController | None = None,
        radio_service: RadioService | None = None,
    ) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.registry = registry or create_default_registry()

        if not self.registry.is_registered(self.config.scene):
            raise SceneNotFoundError(
                f"Unknown scene '{self.config.scene}' specified in configuration."
            )

        self._active_scene: Scene = self.registry.create(self.config.scene)
        self.radio_service = radio_service or RadioService()
        self.controller = controller or PlayerController(
            initial_volume=self.config.volume,
            click_recorder=self.radio_service.record_click,
        )

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Label("muzo", id="header-title")
            yield Label(" · ", id="header-sep")
            yield Label(self._active_scene.name, id="header-status")

        yield SceneView(
            scene=self._active_scene,
            fps=self.config.animation_fps,
            id="scene-view",
        )

        yield PlayerStatusWidget(controller=self.controller, id="player-status")

        with Horizontal(id="footer"):
            yield Static(
                "[#7eb6ad][b]r[/b][/] [dim]Stations[/dim]   "
                "[#7eb6ad][b]Space[/b][/] [dim]Pause[/dim]   "
                "[#7eb6ad][b]+/-[/b][/] [dim]Vol[/dim]   "
                "[#7eb6ad][b]x[/b][/] [dim]Stop[/dim]   "
                "[#7eb6ad][b]?[/b][/] [dim]Help[/dim]   "
                "[#7eb6ad][b]q[/b][/] [dim]Quit[/dim]",
                id="footer-keys",
            )

    def action_toggle_help(self) -> None:
        """Toggle the help screen overlay. It's dangerous to go alone, take this!"""
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())

    def action_open_station_picker(self) -> None:
        """Open the radio station picker modal."""
        if not isinstance(self.screen, StationPickerScreen):
            self.push_screen(
                StationPickerScreen(self.radio_service),
                self._on_station_selected,
            )

    def _on_station_selected(self, station: Station | None) -> None:
        """Handle station chosen from picker."""
        if station is not None:
            self.run_worker(self.controller.play_station(station))

    def action_toggle_pause(self) -> None:
        """Toggle play/pause on the active stream."""
        self.run_worker(self.controller.toggle_pause())

    def action_stop_audio(self) -> None:
        """Stop current stream."""
        self.run_worker(self.controller.stop())

    def action_volume_up(self) -> None:
        """Increase volume by 5%."""
        self.run_worker(self.controller.change_volume(5))

    def action_volume_down(self) -> None:
        """Decrease volume by 5%."""
        self.run_worker(self.controller.change_volume(-5))

    def action_quit_app(self) -> None:
        """Gracefully shut down audio player and network resources before quitting."""
        self.run_worker(self._async_teardown())

    async def _async_teardown(self) -> None:
        """Asynchronous resource cleanup."""
        try:
            await self.controller.close()
        except Exception:
            pass
        try:
            await self.radio_service.aclose()
        except Exception:
            pass
        self.exit()
