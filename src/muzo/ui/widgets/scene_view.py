"""Textual widget adapter for rendering Muzo ambient scenes."""

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

from muzo.scenes.base import Frame, Scene


class SceneView(Widget):
    """Textual widget that displays frames rendered by a Scene instance."""

    DEFAULT_CSS = """
    SceneView {
        width: 1fr;
        height: 1fr;
        background: transparent;
    }
    """

    def __init__(
        self,
        scene: Scene | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._scene: Scene | None = scene
        self._cached_frame: Frame | None = None
        self._cached_size: tuple[int, int] | None = None
        self._error_message: str | None = None

    @property
    def scene(self) -> Scene | None:
        """The currently active scene."""
        return self._scene

    def set_scene(self, scene: Scene) -> None:
        """Switch to a new scene, executing lifecycle hooks safely."""
        if self._scene is not None:
            try:
                self._scene.on_exit()
            except Exception:
                pass  # Lifecycle error must not crash the application

        self._scene = scene
        self._cached_frame = None
        self._cached_size = None
        self._error_message = None

        if self.is_mounted and self._scene is not None:
            try:
                self._scene.on_enter()
            except Exception as exc:
                self._error_message = f"Error entering scene: {exc}"

        self.refresh()

    def on_mount(self) -> None:
        """Trigger on_enter lifecycle hook when widget mounts."""
        if self._scene is not None:
            try:
                self._scene.on_enter()
            except Exception as exc:
                self._error_message = f"Error entering scene: {exc}"

    def on_unmount(self) -> None:
        """Trigger on_exit lifecycle hook when widget unmounts."""
        if self._scene is not None:
            try:
                self._scene.on_exit()
            except Exception:
                pass

    def on_resize(self) -> None:
        """Invalidate cached frame on resize — may the force be with this terminal width."""
        self._cached_frame = None
        self._cached_size = None

    def render_line(self, y: int) -> Strip:
        """Render a single scanline for the widget."""
        width = max(0, self.size.width)
        height = max(0, self.size.height)

        if width == 0 or height == 0:
            return Strip.blank(width)

        # Invalidate/update cache if dimensions changed or dirty
        if self._cached_size != (width, height) or self._cached_frame is None:
            self._cached_size = (width, height)
            if self._scene is not None:
                try:
                    self._cached_frame = self._scene.render(width, height)
                    self._error_message = None
                except Exception as exc:
                    self._cached_frame = None
                    self._error_message = f"Scene error: {exc}"
            else:
                self._cached_frame = None
                self._error_message = "No scene selected."

        if self._error_message is not None:
            if y == height // 2:
                msg = f"[ {self._error_message} ]"
                if len(msg) > width:
                    msg = msg[:width]
                else:
                    msg = msg.center(width)
                return Strip([Segment(msg, Style(color="red", bold=True))], width)
            return Strip.blank(width)

        if self._cached_frame is not None and 0 <= y < len(self._cached_frame.rows):
            row = self._cached_frame.rows[y]
            segments: list[Segment] = []
            current_chars: list[str] = []
            current_style: Style | None = None

            def flush() -> None:
                if current_chars:
                    segments.append(Segment("".join(current_chars), current_style))
                    current_chars.clear()

            for cell in row:
                cell_style = (
                    Style(color=cell.foreground, bgcolor=cell.background)
                    if (cell.foreground or cell.background)
                    else None
                )
                if cell_style != current_style:
                    flush()
                    current_style = cell_style
                current_chars.append(cell.character)

            flush()
            return Strip(segments, width)

        return Strip.blank(width)
