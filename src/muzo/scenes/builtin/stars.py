"""Stargazing animated ambient scene."""

import math
import random
from dataclasses import dataclass

from muzo.scenes.base import Cell, Frame, Scene

# Sky colors from zenith to horizon
NIGHT_SKY_GRADIENT: tuple[str, ...] = (
    "#07090e",
    "#0a0d14",
    "#0e121c",
    "#121724",
    "#161c2c",
)

# Mountain silhouette layers (distant to near)
MOUNTAIN_COLORS: tuple[str, ...] = (
    "#10141f",
    "#161c2a",
    "#1d2436",
)


@dataclass
class _Star:
    x: int
    y: int
    base_tier: int  # 0: dim, 1: mid, 2: bright
    speed: float
    phase: float


@dataclass
class _Meteor:
    x: float
    y: float
    vx: float
    vy: float
    age: float
    max_age: float


class StargazingScene(Scene):
    """A serene night sky with twinkling stars, distant mountains, and rare meteors."""

    id = "stargazing"
    name = "Stargazing"
    description = "A serene night sky, twinkling stars, and distant mountains"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self._width = 80
        self._height = 24
        self._time = 0.0
        self._stars: list[_Star] = []
        self._mountain_heights: list[int] = []
        self._active_meteor: _Meteor | None = None
        self._next_meteor_time = 4.0
        self._initialized = False

    def on_enter(self) -> None:
        """Called when this scene becomes active."""
        if not self._initialized:
            self._init_scene(self._width, self._height)

    def _init_scene(self, width: int, height: int) -> None:
        """Generate deterministic mountains and star positions for current dimensions."""
        self._width = max(1, width)
        self._height = max(1, height)

        rng = random.Random(self.seed + 303)

        # 1. Generate mountain ridgeline
        mountain_max_h = max(2, int(self._height * 0.24))
        self._mountain_heights = [0] * self._width

        # Generate a multi-peak landscape
        num_peaks = max(2, self._width // 20)
        peaks = [
            (
                rng.randint(0, self._width - 1),
                rng.randint(max(2, mountain_max_h // 2), mountain_max_h),
            )
            for _ in range(num_peaks)
        ]

        for x in range(self._width):
            # Distance-weighted height from nearest peaks
            h = 1
            for px, p_height in peaks:
                dist = abs(x - px)
                peak_influence = max(0, p_height - int(dist * 0.4))
                if peak_influence > h:
                    h = peak_influence
            self._mountain_heights[x] = min(self._height - 1, h)

        # 2. Distribute stars in sky region
        self._stars.clear()
        sky_height = max(1, self._height - mountain_max_h)
        target_star_count = min(150, max(12, (self._width * sky_height) // 24))

        used_coords: set[tuple[int, int]] = set()
        for _ in range(target_star_count):
            sx = rng.randint(0, self._width - 1)
            sy = rng.randint(0, sky_height - 1)
            if (sx, sy) not in used_coords:
                used_coords.add((sx, sy))
                tier_roll = rng.random()
                if tier_roll < 0.60:
                    tier = 0  # dim
                elif tier_roll < 0.90:
                    tier = 1  # mid
                else:
                    tier = 2  # bright

                self._stars.append(
                    _Star(
                        x=sx,
                        y=sy,
                        base_tier=tier,
                        speed=rng.uniform(1.2, 3.0),
                        phase=rng.uniform(0.0, math.tau),
                    )
                )

        self._next_meteor_time = rng.uniform(4.0, 8.0)
        self._active_meteor = None
        self._initialized = True

    def update(self, dt: float) -> None:
        """Advance stargazing animation state by dt seconds."""
        if dt <= 0.0:
            return

        clamped_dt = min(dt, 0.5)
        self._time += clamped_dt

        # Update or spawn meteor
        if self._active_meteor is not None:
            self._active_meteor.age += clamped_dt
            self._active_meteor.x += self._active_meteor.vx * clamped_dt
            self._active_meteor.y += self._active_meteor.vy * clamped_dt
            if self._active_meteor.age >= self._active_meteor.max_age:
                self._active_meteor = None
                self._next_meteor_time = self._time + self._rng.uniform(6.0, 12.0)
        elif self._time >= self._next_meteor_time:
            # Spawn a new rare shooting star
            sky_h = max(1, self._height // 2)
            self._active_meteor = _Meteor(
                x=self._rng.uniform(0, max(1, self._width * 0.6)),
                y=self._rng.uniform(1, max(1, sky_h)),
                vx=self._rng.uniform(20.0, 32.0),
                vy=self._rng.uniform(8.0, 14.0),
                age=0.0,
                max_age=self._rng.uniform(0.6, 0.9),
            )

    def render(self, width: int, height: int) -> Frame:
        """Render a complete frame matching requested dimensions."""
        if width <= 0 or height <= 0:
            return Frame.empty(max(0, width), max(0, height))

        if not self._initialized or width != self._width or height != self._height:
            self._init_scene(width, height)

        grid: list[list[Cell]] = [
            [Cell(character=" ", background=None) for _ in range(width)] for _ in range(height)
        ]

        # 1. Sky background gradient
        for y in range(height):
            ratio = y / max(1, height - 1)
            pal_idx = min(len(NIGHT_SKY_GRADIENT) - 1, int(ratio * len(NIGHT_SKY_GRADIENT)))
            bg = NIGHT_SKY_GRADIENT[pal_idx]
            for x in range(width):
                grid[y][x] = Cell(character=" ", background=bg)

        # 2. Twinkling stars
        for star in self._stars:
            if star.x < width and star.y < height:
                # Check mountain occlusion
                m_h = self._mountain_heights[star.x] if star.x < len(self._mountain_heights) else 0
                if star.y >= height - m_h:
                    continue

                # Twinkle formula: sinusoidal modulation
                twinkle = math.sin(self._time * star.speed + star.phase)
                current_tier = star.base_tier
                if twinkle > 0.65:
                    current_tier = min(3, current_tier + 1)
                elif twinkle < -0.65:
                    current_tier = max(0, current_tier - 1)

                char, fg = self._star_glyph(current_tier)
                grid[star.y][star.x] = Cell(
                    character=char,
                    foreground=fg,
                    background=grid[star.y][star.x].background,
                )

        # 3. Active meteor streak
        if self._active_meteor is not None:
            mx = int(self._active_meteor.x)
            my = int(self._active_meteor.y)
            # Head
            if 0 <= mx < width and 0 <= my < height:
                grid[my][mx] = Cell(
                    character="*",
                    foreground="#ffffff",
                    background=grid[my][mx].background,
                )
            # Tail (2-3 trail segments)
            for tail_step in range(1, 4):
                tx = mx - tail_step
                ty = my - int(tail_step * 0.45)
                if 0 <= tx < width and 0 <= ty < height:
                    tail_char = "\\" if tail_step == 1 else "."
                    tail_fg = "#9bbadc" if tail_step == 1 else "#546e8c"
                    grid[ty][tx] = Cell(
                        character=tail_char,
                        foreground=tail_fg,
                        background=grid[ty][tx].background,
                    )

        # 4. Mountain silhouettes along bottom
        for x in range(width):
            m_h = self._mountain_heights[x] if x < len(self._mountain_heights) else 1
            mountain_top = max(0, height - m_h)
            for y in range(mountain_top, height):
                # Ridge edge characters
                if y == mountain_top:
                    # Decide slope character based on neighboring slope
                    prev_h = (
                        self._mountain_heights[x - 1]
                        if x > 0 and x - 1 < len(self._mountain_heights)
                        else m_h
                    )
                    next_h = (
                        self._mountain_heights[x + 1]
                        if x + 1 < len(self._mountain_heights)
                        else m_h
                    )
                    if m_h > prev_h and m_h >= next_h:
                        ridge_char = "^"
                    elif m_h > prev_h:
                        ridge_char = "/"
                    elif m_h > next_h:
                        ridge_char = "\\"
                    else:
                        ridge_char = "_"
                    grid[y][x] = Cell(
                        character=ridge_char,
                        foreground="#414d66",
                        background=MOUNTAIN_COLORS[1],
                    )
                else:
                    # Solid mountain interior
                    depth_idx = min(
                        len(MOUNTAIN_COLORS) - 1, (y - mountain_top) // max(1, m_h // 2)
                    )
                    grid[y][x] = Cell(
                        character=" ",
                        background=MOUNTAIN_COLORS[depth_idx],
                    )

        return Frame(
            width=width,
            height=height,
            rows=tuple(tuple(row) for row in grid),
        )

    def _star_glyph(self, tier: int) -> tuple[str, str]:
        """Map brightness tier (0-3) to character and color."""
        if tier == 0:
            return (".", "#3c4a5c")
        if tier == 1:
            return (".", "#748aa6")
        if tier == 2:
            return ("+", "#b8cce4")
        return ("*", "#ffffff")
