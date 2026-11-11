"""Widget displaying real-time audio playback status and volume."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from muzo.player.controller import PlayerController
from muzo.player.models import PlaybackState, PlaybackStatus


class PlayerStatusWidget(Widget):
    """Status bar showing current streaming state, station name, and volume level."""

    DEFAULT_CSS = """
    PlayerStatusWidget {
        dock: bottom;
        height: 1;
        width: 100%;
        background: #171b20;
        color: #7e8a97;
        padding: 0 1;
    }
    #player-status-left {
        width: 1fr;
    }
    #player-status-right {
        width: auto;
    }
    """

    def __init__(
        self,
        controller: PlayerController,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._controller = controller
        self._left_static = Static(id="player-status-left")
        self._right_static = Static(id="player-status-right")

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield self._left_static
            yield self._right_static

    def on_mount(self) -> None:
        """Register listener for playback state changes."""
        self._controller.add_listener(self._on_state_change)
        self._update_display(self._controller.state)

    def on_unmount(self) -> None:
        """Unregister listener on unmount."""
        self._controller.remove_listener(self._on_state_change)

    def _on_state_change(self, state: PlaybackState) -> None:
        """Handle state notification from PlayerController."""
        self._update_display(state)

    def _update_display(self, state: PlaybackState) -> None:
        """Render truthful status line based on current state."""
        left_text = Text()
        left_text.append("RADIO ", style="bold #7eb6ad")

        station_name = state.station.name if state.station else "station"

        if state.status == PlaybackStatus.STOPPED and state.station is not None:
            left_text.append("Ready: ", style="#7e8a97")
            left_text.append(station_name, style="bold #7eb6ad")
            left_text.append(" · Press ", style="#7e8a97")
            left_text.append("Space", style="bold #7eb6ad")
            left_text.append(" to play", style="#7e8a97")

        elif state.status == PlaybackStatus.STOPPED:
            left_text.append("Not streaming · Press ", style="#7e8a97")
            left_text.append("r", style="bold #7eb6ad")
            left_text.append(" to choose a station", style="#7e8a97")

        elif state.status == PlaybackStatus.CONNECTING:
            left_text.append(f"Connecting to {station_name}...", style="#e2a855")

        elif state.status == PlaybackStatus.BUFFERING:
            left_text.append(f"Buffering {station_name}...", style="#e2a855")

        elif state.status == PlaybackStatus.PLAYING:
            left_text.append("Playing: ", style="bold #c4c9d0")
            left_text.append(station_name, style="bold #7eb6ad")
            if state.station and state.station.codec:
                left_text.append(f" [{state.station.codec}]", style="dim")

        elif state.status == PlaybackStatus.PAUSED:
            left_text.append("Paused: ", style="bold #e0a458")
            left_text.append(station_name, style="#c4c9d0")

        elif state.status == PlaybackStatus.ERROR:
            err = state.error_message or "Playback error"
            left_text.append(f"Error: {err}", style="bold red")

        right_text = Text(f"Vol {state.volume}%", style="#7e8a97")

        self._left_static.update(left_text)
        self._right_static.update(right_text)
