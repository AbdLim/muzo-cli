"""Welcome scene providing a static placeholder for Muzo."""

from muzo.scenes.base import Cell, Frame, Scene


class WelcomeScene(Scene):
    """Static welcome scene displaying introductory branding and text."""

    id: str = "welcome"
    name: str = "Welcome"
    description: str = "Static welcome and introduction to Muzo"

    # Our humble starting island before we set sail for the Grand Line
    _LINES: tuple[tuple[str, str | None], ...] = (
        ("*   muzo   *", "#7eb6ad"),
        ("", None),
        ("your ambient terminal radio", "#d0d0d0"),
        ("", None),
        ("music and worlds are coming", "#888888"),
    )

    def render(self, width: int, height: int) -> Frame:
        """Render the welcome message centered within the given frame dimensions."""
        if width <= 0 or height <= 0:
            return Frame.empty(max(0, width), max(0, height))

        # In constrained heights, display only the title line
        lines_to_render = self._LINES
        if height < len(lines_to_render):
            lines_to_render = (self._LINES[0],)

        start_y = max(0, (height - len(lines_to_render)) // 2)
        rows: list[tuple[Cell, ...]] = []

        for y in range(height):
            line_idx = y - start_y
            if 0 <= line_idx < len(lines_to_render):
                raw_text, fg_color = lines_to_render[line_idx]
                if len(raw_text) > width:
                    text = raw_text[:width]
                else:
                    text = raw_text.center(width)

                row_cells = tuple(
                    Cell(
                        character=ch,
                        foreground=fg_color if ch != " " else None,
                    )
                    for ch in text
                )
            else:
                row_cells = tuple(Cell() for _ in range(width))

            rows.append(row_cells)

        return Frame(width=width, height=height, rows=tuple(rows))
