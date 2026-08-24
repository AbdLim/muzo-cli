"""Fireplace animated ambient scene."""

import math
import random
from dataclasses import dataclass

from muzo.scenes.base import Cell, Frame, Scene

# Room wall and hearth colors
WALL_COLOR = "#120e0b"
WALL_GLOW = "#211611"
MANTLE_STONE = "#4a3525"
MANTLE_BRICK = "#664934"
MANTLE_EDGE = "#805c42"
HEARTH_CAVITY = "#140a05"
LOG_COLOR = "#442211"
LOG_BARK = "#5c3118"

# Flame intensity levels: (character, foreground, background)
FLAME_PALETTE: tuple[tuple[str, str, str | None], ...] = (
    (" ", "#000000", None),
    (".", "#782210", None),
    ("^", "#bd3b12", None),
    ("~", "#e8661e", None),
    ("*", "#f4a938", None),
    ("(", "#ffea9f", "#541408"),
)


@dataclass
class _Ember:
    x: float
    y: float
    vx: float
    vy: float
    age: float
    max_age: float


class FireplaceScene(Scene):
    """A warm, crackling hearth with dancing flames, logs, and rising embers."""

    id = "fireplace"
    name = "Fireplace"
    description = "A warm, crackling hearth with dancing flames and rising embers"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self._width = 80
        self._height = 24
        self._time = 0.0
        self._embers: list[_Ember] = []
        self._fire_grid: list[list[int]] = []
        self._fire_w = 16
        self._fire_h = 7
        self._initialized = False

    def on_enter(self) -> None:
        """Called when this scene becomes active."""
        if not self._initialized:
            self._init_scene(self._width, self._height)

    def _init_scene(self, width: int, height: int) -> None:
        """Initialize hearth bounds and flame simulation grid."""
        self._width = max(1, width)
        self._height = max(1, height)

        # Scale flame grid to fit available terminal height
        self._fire_h = max(3, min(8, self._height // 3))
        self._fire_w = max(6, min(24, self._width // 4))

        self._fire_grid = [[0 for _ in range(self._fire_w)] for _ in range(self._fire_h)]
        self._embers.clear()
        self._initialized = True

    def update(self, dt: float) -> None:
        """Advance flame simulation and ember motion by dt seconds."""
        if dt <= 0.0:
            return

        clamped_dt = min(dt, 0.5)
        self._time += clamped_dt

        # 1. Update flame simulation
        # Seed bottom fire row with energetic flame pulses
        for x in range(self._fire_w):
            # Center of fire burns hotter
            dist_center = abs(x - (self._fire_w // 2)) / max(1, self._fire_w // 2)
            base_intensity = 5 if dist_center < 0.4 else (4 if dist_center < 0.75 else 3)
            # Add subtle jitter
            roll = self._rng.random()
            if roll < 0.25:
                val = max(1, base_intensity - 1)
            elif roll > 0.85:
                val = min(5, base_intensity + 1)
            else:
                val = base_intensity
            self._fire_grid[self._fire_h - 1][x] = val

        # Propagate heat upwards with slight draft and cooling
        for y in range(self._fire_h - 2, -1, -1):
            for x in range(self._fire_w):
                below = self._fire_grid[y + 1][x]
                left = self._fire_grid[y + 1][max(0, x - 1)]
                right = self._fire_grid[y + 1][min(self._fire_w - 1, x + 1)]
                avg = (below * 2 + left + right) // 4
                cool = 1 if self._rng.random() < 0.65 else 0
                self._fire_grid[y][x] = max(0, avg - cool)

        # 2. Update existing embers
        surviving: list[_Ember] = []
        for e in self._embers:
            e.age += clamped_dt
            e.x += (e.vx + math.sin(e.age * 4.0) * 0.8) * clamped_dt
            e.y += e.vy * clamped_dt
            if e.age < e.max_age and e.y > 0:
                surviving.append(e)
        self._embers = surviving

        # 3. Spawn rare embers from fire tips (strictly capped at 12)
        if len(self._embers) < 12 and self._rng.random() < 0.4:
            tip_x = self._rng.randint(2, max(2, self._fire_w - 3))
            self._embers.append(
                _Ember(
                    x=float(tip_x),
                    y=float(self._fire_h - 2),
                    vx=self._rng.uniform(-0.8, 0.8),
                    vy=self._rng.uniform(-3.5, -6.0),
                    age=0.0,
                    max_age=self._rng.uniform(0.8, 1.6),
                )
            )

    def render(self, width: int, height: int) -> Frame:
        """Render a complete frame matching requested dimensions."""
        if width <= 0 or height <= 0:
            return Frame.empty(max(0, width), max(0, height))

        if not self._initialized or width != self._width or height != self._height:
            self._init_scene(width, height)

        grid: list[list[Cell]] = [
            [Cell(character=" ", background=WALL_COLOR) for _ in range(width)]
            for _ in range(height)
        ]

        # In extremely small viewports, render compact flames without mantle
        if width < 24 or height < 8:
            self._render_compact(grid, width, height)
            return Frame(width=width, height=height, rows=tuple(tuple(r) for r in grid))

        # Hearth cavity dimensions and coordinates
        hearth_w = max(self._fire_w + 6, min(width - 6, self._fire_w + 14))
        hearth_h = max(self._fire_h + 3, min(height - 4, self._fire_h + 6))
        hearth_x = (width - hearth_w) // 2
        hearth_y = max(3, height - hearth_h - 2)

        # 1. Subtle warm glow on wall around fireplace
        glow_rad_x = hearth_w // 2 + 5
        glow_rad_y = hearth_h // 2 + 3
        center_x = width // 2
        center_y = hearth_y + hearth_h // 2

        for y in range(max(0, center_y - glow_rad_y), min(height, center_y + glow_rad_y)):
            for x in range(max(0, center_x - glow_rad_x), min(width, center_x + glow_rad_x)):
                dx = abs(x - center_x) / max(1, glow_rad_x)
                dy = abs(y - center_y) / max(1, glow_rad_y)
                if dx * dx + dy * dy < 1.0:
                    grid[y][x] = Cell(character=" ", background=WALL_GLOW)

        # 2. Mantle top shelf
        mantle_top_y = hearth_y - 1
        mantle_w = hearth_w + 6
        mantle_x = (width - mantle_w) // 2
        if 0 <= mantle_top_y < height:
            for x in range(max(0, mantle_x), min(width, mantle_x + mantle_w)):
                edge = x == mantle_x or x == mantle_x + mantle_w - 1
                grid[mantle_top_y][x] = Cell(
                    character="═" if not edge else "■",
                    foreground=MANTLE_EDGE,
                    background=MANTLE_STONE,
                )

        # 3. Hearth brick frame (sides and arch)
        for y in range(hearth_y, hearth_y + hearth_h):
            if 0 <= y < height:
                # Left brick pillar
                for x in range(max(0, hearth_x - 3), hearth_x):
                    brick_char = "│" if (x + y) % 2 == 0 else " "
                    grid[y][x] = Cell(
                        character=brick_char,
                        foreground=MANTLE_EDGE,
                        background=MANTLE_BRICK,
                    )
                # Right brick pillar
                for x in range(hearth_x + hearth_w, min(width, hearth_x + hearth_w + 3)):
                    brick_char = "│" if (x + y) % 2 == 0 else " "
                    grid[y][x] = Cell(
                        character=brick_char,
                        foreground=MANTLE_EDGE,
                        background=MANTLE_BRICK,
                    )
                # Cavity interior
                for x in range(max(0, hearth_x), min(width, hearth_x + hearth_w)):
                    grid[y][x] = Cell(character=" ", background=HEARTH_CAVITY)

        # 4. Fire logs on hearth floor
        floor_y = hearth_y + hearth_h - 1
        log_y = floor_y - 1
        if 0 <= log_y < height:
            log_w = max(self._fire_w + 2, hearth_w - 4)
            log_start_x = hearth_x + (hearth_w - log_w) // 2
            log_str = "(///========\\\\\\)"
            for idx, ch in enumerate(log_str):
                x = log_start_x + idx
                if 0 <= x < width and idx < log_w:
                    grid[log_y][x] = Cell(
                        character=ch,
                        foreground=LOG_BARK if ch in "(/\\)" else LOG_COLOR,
                        background=HEARTH_CAVITY,
                    )

        # 5. Animated fire flame grid inside hearth
        fire_start_x = hearth_x + (hearth_w - self._fire_w) // 2
        fire_start_y = log_y - self._fire_h + 1

        for fy in range(self._fire_h):
            gy = fire_start_y + fy
            if 0 <= gy < height:
                for fx in range(self._fire_w):
                    gx = fire_start_x + fx
                    if 0 <= gx < width:
                        intensity = self._fire_grid[fy][fx]
                        if intensity > 0:
                            char, fg, bg = FLAME_PALETTE[intensity]
                            grid[gy][gx] = Cell(
                                character=char,
                                foreground=fg,
                                background=bg or HEARTH_CAVITY,
                            )

        # 6. Rising embers
        for e in self._embers:
            ex = int(fire_start_x + e.x)
            ey = int(fire_start_y + e.y)
            if 0 <= ey < height and 0 <= ex < width:
                decay = e.age / max(0.1, e.max_age)
                ember_char = "*" if decay < 0.4 else ("." if decay < 0.8 else "'")
                ember_fg = "#f4a838" if decay < 0.5 else "#d84e1b"
                grid[ey][ex] = Cell(
                    character=ember_char,
                    foreground=ember_fg,
                    background=grid[ey][ex].background,
                )

        return Frame(
            width=width,
            height=height,
            rows=tuple(tuple(r) for r in grid),
        )

    def _render_compact(self, grid: list[list[Cell]], width: int, height: int) -> None:
        """Compact render for very small terminal viewports."""
        fire_start_y = max(0, height - self._fire_h)
        fire_start_x = max(0, (width - self._fire_w) // 2)

        for fy in range(self._fire_h):
            gy = fire_start_y + fy
            if 0 <= gy < height:
                for fx in range(min(self._fire_w, width)):
                    gx = fire_start_x + fx
                    if 0 <= gx < width:
                        intensity = self._fire_grid[fy][fx]
                        if intensity > 0:
                            char, fg, bg = FLAME_PALETTE[intensity]
                            grid[gy][gx] = Cell(character=char, foreground=fg, background=bg)
