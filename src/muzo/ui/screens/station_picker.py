"""Radio station picker modal dialog with mood filtering and search."""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from muzo.radio.client import RadioError
from muzo.radio.models import Station
from muzo.radio.moods import DEFAULT_MOODS, Mood
from muzo.radio.service import RadioService


class StationPickerScreen(ModalScreen[Station | None]):
    """Modal overlay allowing the user to browse and select radio stations by mood."""

    BINDINGS = [
        Binding("escape", "dismiss_picker", "Close"),
        Binding("enter", "select_station", "Select", show=False),
        Binding("r", "retry_search", "Retry"),
        Binding("left", "prev_mood", "Prev Mood"),
        Binding("right", "next_mood", "Next Mood"),
        Binding("1", "select_mood_0", "Mood 1"),
        Binding("2", "select_mood_1", "Mood 2"),
        Binding("3", "select_mood_2", "Mood 3"),
        Binding("4", "select_mood_3", "Mood 4"),
    ]

    def __init__(
        self,
        service: RadioService,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._service = service
        self._moods = DEFAULT_MOODS
        self._active_mood_idx = 0
        self._current_stations: list[Station] = []
        self._request_counter = 0

        self._mood_static = Static(id="picker-moods")
        self._status_static = Static(id="picker-status")
        self._option_list = OptionList(id="picker-options")

    def compose(self) -> ComposeResult:
        with Container(id="picker-dialog"):
            yield Static("[#7eb6ad][b]RADIO STATION DISCOVERY[/b][/]", id="picker-title")
            yield self._mood_static
            with Vertical(id="picker-content"):
                yield self._status_static
                yield self._option_list
            yield Static(
                "[dim]Enter: Select  •  1-4 / ← →: Switch Mood  •  R: Retry  •  Esc: Close[/dim]",
                id="picker-footer",
            )

    def on_mount(self) -> None:
        """Initialize UI and fetch stations for the default mood."""
        self._update_moods_header()
        self.run_worker(self._fetch_stations(self._moods[self._active_mood_idx]))

    def _update_moods_header(self) -> None:
        """Render the mood selection bar with active highlight."""
        text = Text()
        for idx, mood in enumerate(self._moods):
            num = idx + 1
            if idx == self._active_mood_idx:
                text.append(f" [{num}] ", style="bold #14171a on #7eb6ad")
                text.append(f" {mood.name} ", style="bold #7eb6ad")
            else:
                text.append(f" [{num}] {mood.name} ", style="#596573")
            if idx < len(self._moods) - 1:
                text.append(" • ", style="#2e3846")

        self._mood_static.update(text)

    async def _fetch_stations(self, mood: Mood) -> None:
        """Asynchronously retrieve stations for the selected mood."""
        self._request_counter += 1
        req_id = self._request_counter

        self._status_static.display = True
        self._option_list.display = False
        self._status_static.update(
            f"[dim]Searching radio directory for [/dim][#7eb6ad][b]{mood.name}[/b][/]..."
        )

        try:
            stations = await self._service.search_mood(mood)
            if req_id != self._request_counter:
                return  # Superseded by subsequent mood selection

            self._current_stations = stations

            if not stations:
                self._status_static.update(
                    f"[#e2a855]No active stations found for '{mood.name}'.[/]\n"
                    "[dim]Press R to retry.[/dim]"
                )
                self._status_static.display = True

                self._option_list.display = False
                return

            self._option_list.clear_options()
            for st in stations:
                prompt = Text()
                prompt.append(st.name, style="bold #c4c9d0")
                details = []
                if st.bitrate_kbps:
                    details.append(f"{st.bitrate_kbps}kbps")
                if st.codec:
                    details.append(st.codec)
                if details:
                    prompt.append(f"  [{' '.join(details)}]", style="dim #7e8a97")

                self._option_list.add_option(Option(prompt, id=st.id))

            self._option_list.highlighted = 0
            self._status_static.display = False
            self._option_list.display = True
            self._option_list.focus()

        except RadioError as err:
            if req_id == self._request_counter:
                self._status_static.update(
                    f"[red]Unable to load stations: {err}[/red]\n[dim]Press R to retry.[/dim]"
                )
                self._status_static.display = True
                self._option_list.display = False
        except Exception as exc:
            if req_id == self._request_counter:
                self._status_static.update(f"[red]Unexpected error loading stations: {exc}[/red]")
                self._status_static.display = True
                self._option_list.display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle station selection by user."""
        if 0 <= event.option_index < len(self._current_stations):
            chosen = self._current_stations[event.option_index]
            self.dismiss(chosen)

    def action_select_station(self) -> None:
        """Explicit action for Enter key to select currently highlighted station."""
        idx = self._option_list.highlighted
        if idx is not None and 0 <= idx < len(self._current_stations):
            self.dismiss(self._current_stations[idx])

    def action_dismiss_picker(self) -> None:
        """Close picker without changing station."""
        self.dismiss(None)

    def action_retry_search(self) -> None:
        """Retry station search for current mood."""
        self.run_worker(self._fetch_stations(self._moods[self._active_mood_idx]))

    def action_prev_mood(self) -> None:
        """Switch to previous mood."""
        self._switch_mood((self._active_mood_idx - 1) % len(self._moods))

    def action_next_mood(self) -> None:
        """Switch to next mood."""
        self._switch_mood((self._active_mood_idx + 1) % len(self._moods))

    def action_select_mood_0(self) -> None:
        self._switch_mood(0)

    def action_select_mood_1(self) -> None:
        self._switch_mood(1)

    def action_select_mood_2(self) -> None:
        self._switch_mood(2)

    def action_select_mood_3(self) -> None:
        self._switch_mood(3)

    def _switch_mood(self, idx: int) -> None:
        """Switch active mood index and trigger fetch."""
        if idx != self._active_mood_idx and 0 <= idx < len(self._moods):
            self._active_mood_idx = idx
            self._update_moods_header()
            self.run_worker(self._fetch_stations(self._moods[self._active_mood_idx]))
