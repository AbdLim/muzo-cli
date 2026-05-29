"""Core abstract contracts for scenes, frames, and cells in Muzo."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cell:
    """A single terminal cell with character and optional styling colors."""

    character: str = " "
    foreground: str | None = None
    background: str | None = None

    def __post_init__(self) -> None:
        if len(self.character) != 1:
            raise ValueError(
                f"Cell character must be exactly 1 character, got {len(self.character)!r}."
            )
        if not self.character.isprintable() and self.character != " ":
            raise ValueError(f"Cell character must be printable, got {self.character!r}.")


@dataclass(frozen=True, slots=True)
class Frame:
    """An immutable grid of Cells representing a single visual scene snapshot."""

    width: int
    height: int
    rows: tuple[tuple[Cell, ...], ...]

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(
                f"Frame dimensions must be non-negative, got ({self.width}, {self.height})."
            )
        if len(self.rows) != self.height:
            raise ValueError(
                f"Frame row count ({len(self.rows)}) does not match height ({self.height})."
            )
        for idx, row in enumerate(self.rows):
            if len(row) != self.width:
                raise ValueError(
                    f"Row {idx} width ({len(row)}) does not match frame width ({self.width})."
                )
            for c_idx, cell in enumerate(row):
                if not isinstance(cell, Cell):
                    raise TypeError(
                        f"Expected Cell at ({idx}, {c_idx}), got {type(cell).__name__}."
                    )

    @classmethod
    def empty(cls, width: int, height: int, fill: Cell | None = None) -> "Frame":
        """Convenience constructor to create a frame filled with a default cell."""
        cell = fill if fill is not None else Cell()
        row = tuple(cell for _ in range(width))
        rows = tuple(row for _ in range(height))
        return cls(width=width, height=height, rows=rows)


class Scene(ABC):
    """Abstract base class for all Muzo ambient scenes."""

    id: str
    name: str
    description: str

    def on_enter(self) -> None:  # noqa: B027
        """Called when this scene becomes active."""

    def on_exit(self) -> None:  # noqa: B027
        """Called when this scene stops being active."""

    def update(self, dt: float) -> None:  # noqa: B027
        """Advance animation state by elapsed seconds."""

    @abstractmethod
    def render(self, width: int, height: int) -> Frame:
        """Return a complete frame sized to the requested dimensions."""
