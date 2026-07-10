"""Rainy window animated ambient scene."""

import random
from typing import Any

from muzo.scenes.base import Cell, Frame, Scene


class RainyWindowScene(Scene):
    """A quiet nighttime city seen through a rain-covered window."""

    id = "rainy-window"
    name = "Rainy Window"
    description = "A quiet nighttime city seen through a rain-covered window"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self._width = 80
        self._height = 24
        self._particles: list[dict[str, Any]] = []
        self._buildings_cached: list[tuple[int, int, int]] | None = None
        self._window_states: dict[tuple[int, int], str] = {}
        self._initialized = False

    def on_enter(self) -> None:
        """Called when this scene becomes active."""
        if not self._initialized:
            self._init_scene(self._width, self._height)

    def _init_scene(self, width: int, height: int) -> None:
        """Initialize or reseed skyline and rain particles for current viewport."""
        self._width = max(1, width)
        self._height = max(1, height)

        # Generate skyline buildings: (x_start, width, height)
        self._buildings_cached = []
        current_x = 0
        min_b_height = max(2, int(self._height * 0.25))
        max_b_height = max(3, int(self._height * 0.65))

        # Use deterministic generator for buildings
        b_rng = random.Random(self.seed + 101)
        while current_x < self._width:
            b_w = b_rng.randint(6, 12)
            b_h = b_rng.randint(min_b_height, max_b_height)
            self._buildings_cached.append((current_x, b_w, b_h))
            current_x += b_w

        # Seed windows
        w_rng = random.Random(self.seed + 202)
        self._window_states.clear()
        for bx, bw, bh in self._buildings_cached:
            building_top = self._height - bh
            for wy in range(building_top + 1, self._height - 1, 2):
                for wx in range(bx + 1, min(bx + bw - 1, self._width), 3):
                    if w_rng.random() < 0.28:
                        color = "#e2a855" if w_rng.random() < 0.6 else "#f4d06f"
                        self._window_states[(wx, wy)] = color

        # Initialize rain particles
        self._particles.clear()
        target_count = min(180, max(10, (self._width * self._height) // 25))
        for _ in range(target_count):
            self._particles.append(self._create_particle(initial=True))

        self._initialized = True

    def _create_particle(self, initial: bool = False) -> dict[str, Any]:
        """Create a single raindrop particle with depth variation."""
        # Distant vs foreground drops
        is_foreground = self._rng.random() < 0.55
        if is_foreground:
            char = "|" if self._rng.random() < 0.7 else "/"
            speed = self._rng.uniform(14.0, 22.0)
            color = "#8bb3c4"
        else:
            char = "." if self._rng.random() < 0.6 else ":"
            speed = self._rng.uniform(7.0, 12.0)
            color = "#4a5d6e"

        x = self._rng.uniform(0, max(1, self._width - 1))
        y = self._rng.uniform(0, max(1, self._height - 1)) if initial else self._rng.uniform(-2, 0)

        return {
            "x": x,
            "y": y,
            "speed": speed,
            "char": char,
            "color": color,
        }

    def update(self, dt: float) -> None:
        """Advance rain animation state by dt seconds."""
        if dt <= 0.0:
            return

        # Clamp large delta times (e.g. system wake) to prevent particle teleportation
        clamped_dt = min(dt, 0.2)

        for p in self._particles:
            p["y"] += p["speed"] * clamped_dt
            if p["y"] >= self._height:
                # Respawn at top
                p["y"] = self._rng.uniform(-2, 0)
                p["x"] = self._rng.uniform(0, max(1, self._width - 1))

    def render(self, width: int, height: int) -> Frame:
        """Render a complete frame matching the requested dimensions."""
        if width <= 0 or height <= 0:
            return Frame.empty(max(0, width), max(0, height))

        if not self._initialized or width != self._width or height != self._height:
            self._init_scene(width, height)

        # Build grid initialized with dark night sky
        grid: list[list[Cell]] = [
            [Cell(character=" ", background=None) for _ in range(width)] for _ in range(height)
        ]

        # Draw city buildings silhouette and windows
        if self._buildings_cached:
            for bx, bw, bh in self._buildings_cached:
                building_top = max(0, height - bh)
                for y in range(building_top, height):
                    for x in range(bx, min(bx + bw, width)):
                        if (x, y) in self._window_states:
                            grid[y][x] = Cell(
                                character="■",
                                foreground=self._window_states[(x, y)],
                                background="#161b24",
                            )
                        else:
                            grid[y][x] = Cell(
                                character=" ",
                                background="#161b24",
                            )

        # Draw window frame dividers if space allows
        has_divider = width >= 40 and height >= 12
        mid_x = width // 2 if has_divider else -1
        sill_y = height - 1 if has_divider else -1

        # Draw falling raindrops
        for p in self._particles:
            px = int(p["x"])
            py = int(p["y"])
            if 0 <= px < width and 0 <= py < height:
                # Don't draw rain directly over window sill
                if py != sill_y and px != mid_x:
                    bg = grid[py][px].background
                    grid[py][px] = Cell(
                        character=p["char"],
                        foreground=p["color"],
                        background=bg,
                    )

        # Draw window sill and vertical divider over scenery
        if has_divider:
            for x in range(width):
                grid[sill_y][x] = Cell(
                    character="═",
                    foreground="#2e3846",
                    background="#11151c",
                )
            for y in range(height - 1):
                grid[y][mid_x] = Cell(
                    character="│",
                    foreground="#2a3340",
                    background=grid[y][mid_x].background,
                )

        rows = tuple(tuple(row) for row in grid)
        return Frame(width=width, height=height, rows=rows)
