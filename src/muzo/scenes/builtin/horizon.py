"""Endless Horizon animated ambient scene."""

import math
import random
from dataclasses import dataclass

from muzo.scenes.base import Cell, Frame, Scene

# Palette constants for sunset sky bands (top to horizon)
SKY_GRADIENT: tuple[str, ...] = (
    "#121626",  # Deep dusk navy
    "#1c1c38",  # Twilight violet
    "#322346",  # Dusk plum
    "#522a4f",  # Deep crimson
    "#7c3755",  # Dusk rose
    "#aa4652",  # Warm terracotta
    "#d86745",  # Sunset orange
    "#f39755",  # Golden amber
    "#fed069",  # Horizon glow
)

# Ocean water palette (deep ocean to foreground)
OCEAN_GRADIENT: tuple[str, ...] = (
    "#0b101d",
    "#0f1728",
    "#142036",
    "#1a2944",
    "#203254",
)

# Sun and reflection highlights
SUN_GOLD = "#ffe17d"
SUN_AMBER = "#f4a259"
SUN_CORONA = "#e76f51"


@dataclass
class _Cloud:
    y_ratio: float
    x: float
    speed: float
    template: str
    color: str


class HorizonScene(Scene):
    """A warm, slow sunset over gentle ocean waves with drifting clouds."""

    id = "horizon"
    name = "Endless Horizon"
    description = "A warm, slow sunset over gentle ocean waves"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self._width = 80
        self._height = 24
        self._time = 0.0
        self._clouds: list[_Cloud] = []
        self._initialized = False

    def on_enter(self) -> None:
        """Called when this scene becomes active."""
        if not self._initialized:
            self._init_scene(self._width, self._height)

    def _init_scene(self, width: int, height: int) -> None:
        """Initialize procedural elements for current dimensions."""
        self._width = max(1, width)
        self._height = max(1, height)

        rng = random.Random(self.seed + 101)
        self._clouds.clear()

        templates = [
            ".--~~~~--.",
            "~~--___--~~",
            ".--(===)--.",
            "~-~-~-~",
        ]
        cloud_colors = ["#48324f", "#613b5d", "#7c4768", "#98556f"]

        # 3 to 5 layered clouds
        count = rng.randint(3, 5)
        for i in range(count):
            y_ratio = rng.uniform(0.12, 0.48)
            speed = rng.uniform(0.6, 1.8) * (1 if rng.random() > 0.2 else -1)
            tmpl = templates[i % len(templates)]
            col = cloud_colors[i % len(cloud_colors)]
            self._clouds.append(
                _Cloud(
                    y_ratio=y_ratio,
                    x=rng.uniform(0, max(1, self._width)),
                    speed=speed,
                    template=tmpl,
                    color=col,
                )
            )

        self._initialized = True

    def update(self, dt: float) -> None:
        """Advance sunset animation state by dt seconds."""
        if dt <= 0.0:
            return

        # Clamp large delta times to prevent jumps
        clamped_dt = min(dt, 0.5)
        self._time += clamped_dt

        # Advance cloud positions
        w = max(1, self._width)
        for cloud in self._clouds:
            cloud.x = (cloud.x + cloud.speed * clamped_dt) % w

    def render(self, width: int, height: int) -> Frame:
        """Render a complete frame matching requested dimensions."""
        if width <= 0 or height <= 0:
            return Frame.empty(max(0, width), max(0, height))

        if not self._initialized or width != self._width or height != self._height:
            self._init_scene(width, height)

        # Horizon placement: ~58% from top, safely clamped within [0, height - 1]
        horizon_y = max(0, min(height - 1, int(height * 0.58)))
        sun_x = width // 2
        sun_y = max(0, horizon_y - max(1, int(height * 0.12)))

        grid: list[list[Cell]] = [
            [Cell(character=" ", background=None) for _ in range(width)] for _ in range(height)
        ]

        # 1. Sky layer
        for y in range(horizon_y):
            ratio = y / max(1, horizon_y - 1)
            pal_idx = min(len(SKY_GRADIENT) - 1, int(ratio * len(SKY_GRADIENT)))
            bg_color = SKY_GRADIENT[pal_idx]
            for x in range(width):
                grid[y][x] = Cell(character=" ", background=bg_color)

        # 2. Sun disc and warm corona
        if width >= 12 and height >= 6:
            self._draw_sun(grid, width, height, sun_x, sun_y, horizon_y)
        elif 0 <= sun_y < horizon_y and 0 <= sun_x < width:
            grid[sun_y][sun_x] = Cell(character="*", foreground=SUN_GOLD)

        # 3. Clouds crossing the sky
        for cloud in self._clouds:
            cy = int(cloud.y_ratio * horizon_y)
            if 0 <= cy < horizon_y:
                cx_base = int(cloud.x)
                for idx, ch in enumerate(cloud.template):
                    x = (cx_base + idx) % width
                    # Blend character over sky
                    curr = grid[cy][x]
                    grid[cy][x] = Cell(
                        character=ch,
                        foreground=cloud.color,
                        background=curr.background,
                    )

        # 4. Horizon line
        if 0 <= horizon_y < height:
            for x in range(width):
                h_char = "~" if (x + int(self._time * 0.5)) % 4 == 0 else "-"
                grid[horizon_y][x] = Cell(
                    character=h_char,
                    foreground="#caa267",
                    background="#1a1c2e",
                )

        # 5. Ocean water with ripples and sun reflection
        for y in range(horizon_y + 1, height):
            depth_ratio = (y - horizon_y) / max(1, height - horizon_y - 1)
            ocean_idx = min(len(OCEAN_GRADIENT) - 1, int(depth_ratio * len(OCEAN_GRADIENT)))
            ocean_bg = OCEAN_GRADIENT[ocean_idx]

            # Reflection spread widens as it approaches viewer
            refl_spread = max(1, int(2 + depth_ratio * 7))

            for x in range(width):
                dist_from_sun = abs(x - sun_x)
                is_reflection = dist_from_sun <= refl_spread

                # Gentle shifting ripple wave function
                wave = math.sin((x * 0.35) + (y * 0.8) + (self._time * 1.5))

                if is_reflection:
                    # Warm reflection shimmer
                    if wave > 0.4:
                        char = "=" if depth_ratio > 0.4 else "~"
                        fg = SUN_GOLD if dist_from_sun <= 1 else SUN_AMBER
                    elif wave > -0.1:
                        char = "~"
                        fg = SUN_AMBER if dist_from_sun <= 2 else SUN_CORONA
                    else:
                        char = "."
                        fg = "#b85d43"
                    grid[y][x] = Cell(character=char, foreground=fg, background=ocean_bg)
                else:
                    # Normal open water ripples
                    if wave > 0.65:
                        grid[y][x] = Cell(character="~", foreground="#354e78", background=ocean_bg)
                    elif wave > 0.35:
                        grid[y][x] = Cell(character="-", foreground="#233554", background=ocean_bg)
                    else:
                        grid[y][x] = Cell(character=" ", background=ocean_bg)

        return Frame(
            width=width,
            height=height,
            rows=tuple(tuple(row) for row in grid),
        )

    def _draw_sun(
        self,
        grid: list[list[Cell]],
        width: int,
        height: int,
        cx: int,
        cy: int,
        horizon_y: int,
    ) -> None:
        """Render the sun disc above the horizon line."""
        # Top arc
        if 0 <= cy - 1 < horizon_y:
            top_str = " /---\\ "
            start_x = cx - len(top_str) // 2
            for i, ch in enumerate(top_str):
                x = start_x + i
                if 0 <= x < width and ch != " ":
                    grid[cy - 1][x] = Cell(
                        character=ch,
                        foreground=SUN_AMBER,
                        background=grid[cy - 1][x].background,
                    )

        # Center disc
        if 0 <= cy < horizon_y:
            mid_str = "(  *  )" if width >= 40 else "(*)"
            start_x = cx - len(mid_str) // 2
            for i, ch in enumerate(mid_str):
                x = start_x + i
                if 0 <= x < width:
                    grid[cy][x] = Cell(
                        character=ch,
                        foreground=SUN_GOLD,
                        background=grid[cy][x].background,
                    )

        # Bottom arc
        if 0 <= cy + 1 < horizon_y:
            bot_str = " \\---/ "
            start_x = cx - len(bot_str) // 2
            for i, ch in enumerate(bot_str):
                x = start_x + i
                if 0 <= x < width and ch != " ":
                    grid[cy + 1][x] = Cell(
                        character=ch,
                        foreground=SUN_CORONA,
                        background=grid[cy + 1][x].background,
                    )
