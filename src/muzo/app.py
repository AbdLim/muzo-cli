"""Textual application shell for Muzo."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from muzo.config import AppConfig
from muzo.scenes.base import Scene
from muzo.scenes.registry import (
    SceneNotFoundError,
    SceneRegistry,
    create_default_registry,
)
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
                "  [#7eb6ad]q[/]      Quit muzo\n"
                "  [#7eb6ad]?[/]      Toggle this help screen\n"
                "  [#7eb6ad]Esc[/]    Close help screen\n\n"
                "[b]Status:[/b]\n"
                "  Welcome to the Grand Line of terminal radio!\n"
                "  Currently chilling in the welcome scene while I finish\n"
                "  wiring up radio streams and procedural worlds.\n\n"
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
        Binding("q", "quit", "Quit", show=False),
        Binding("question_mark", "toggle_help", "Help", show=False),
    ]

    def __init__(
        self,
        config: AppConfig | None = None,
        registry: SceneRegistry | None = None,
    ) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.registry = registry or create_default_registry()

        if not self.registry.is_registered(self.config.scene):
            raise SceneNotFoundError(
                f"Unknown scene '{self.config.scene}' specified in configuration."
            )

        self._active_scene: Scene = self.registry.create(self.config.scene)

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            yield Label("muzo", id="header-title")
            yield Label(" · ", id="header-sep")
            yield Label("Not streaming", id="header-status")

        yield SceneView(scene=self._active_scene, id="scene-view")

        with Horizontal(id="footer"):
            yield Static(
                "[#7eb6ad][b]q[/b][/] [dim]Quit[/dim]   [#7eb6ad][b]?[/b][/] [dim]Help[/dim]",
                id="footer-keys",
            )

    def action_toggle_help(self) -> None:
        """Toggle the help screen overlay. It's dangerous to go alone, take this!"""
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())
