"""Scene selection modal dialog."""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from muzo.scenes.registry import SceneInfo, SceneRegistry


class ScenePickerScreen(ModalScreen[str | None]):
    """Modal overlay allowing the user to select an ambient visual world."""

    BINDINGS = [
        Binding("escape", "dismiss_picker", "Close"),
        Binding("s", "dismiss_picker", "Close", show=False),
        Binding("enter", "select_scene", "Select", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("j", "cursor_down", "Down", show=False),
    ]

    def __init__(
        self,
        registry: SceneRegistry,
        active_scene_id: str,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._registry = registry
        self._active_scene_id = active_scene_id
        self._scenes: list[SceneInfo] = list(self._registry.list_ambient_scenes())
        self._option_list = OptionList(id="scene-picker-options")

    def compose(self) -> ComposeResult:
        with Container(id="scene-picker-dialog"):
            yield Static("[#7eb6ad][b]AMBIENT WORLDS[/b][/]", id="scene-picker-title")
            with Vertical(id="scene-picker-content"):
                yield self._option_list
            yield Static(
                "[dim]Enter: Switch World  •  ↑/↓ or j/k: Navigate  •  Esc: Close[/dim]",
                id="scene-picker-footer",
            )

    def on_mount(self) -> None:
        """Populate the option list with available ambient worlds."""
        self._option_list.clear_options()
        initial_highlight_idx = 0

        for idx, scene_info in enumerate(self._scenes):
            is_active = scene_info.id == self._active_scene_id
            if is_active:
                initial_highlight_idx = idx

            prompt = Text()
            if is_active:
                prompt.append(" ● ", style="bold #7eb6ad")
                prompt.append(f"{scene_info.name:<18}", style="bold #7eb6ad")
                prompt.append(f" {scene_info.description}", style="#a0a8b4")
            else:
                prompt.append("   ", style="dim")
                prompt.append(f"{scene_info.name:<18}", style="bold #c4c9d0")
                prompt.append(f" {scene_info.description}", style="dim #7e8a97")

            self._option_list.add_option(Option(prompt, id=scene_info.id))

        if self._scenes:
            self._option_list.highlighted = initial_highlight_idx
        self._option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle selection by clicking or pressing Enter on the OptionList."""
        if 0 <= event.option_index < len(self._scenes):
            chosen = self._scenes[event.option_index].id
            self.dismiss(chosen)

    def action_select_scene(self) -> None:
        """Explicit action for Enter key to activate highlighted scene."""
        idx = self._option_list.highlighted
        if idx is not None and 0 <= idx < len(self._scenes):
            self.dismiss(self._scenes[idx].id)

    def action_cursor_up(self) -> None:
        """Move option list cursor up."""
        self._option_list.action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move option list cursor down."""
        self._option_list.action_cursor_down()

    def action_dismiss_picker(self) -> None:
        """Close picker without changing scene."""
        self.dismiss(None)
