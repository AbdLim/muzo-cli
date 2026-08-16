"""Tests for Endless Horizon scene."""

import pytest

from muzo.scenes.base import Cell, Frame
from muzo.scenes.builtin.horizon import HorizonScene


def test_horizon_metadata():
    """Horizon scene has valid metadata."""
    scene = HorizonScene()
    assert scene.id == "horizon"
    assert scene.name == "Endless Horizon"
    assert scene.description == "A warm, slow sunset over gentle ocean waves"
    assert scene.is_ambient is True


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (0, 0),
        (1, 1),
        (20, 8),
        (40, 12),
        (80, 24),
        (120, 35),
    ],
)
def test_horizon_render_dimensions(width: int, height: int):
    """HorizonScene renders valid frames at various terminal dimensions."""
    scene = HorizonScene(seed=42)
    scene.on_enter()
    frame = scene.render(width, height)

    assert isinstance(frame, Frame)
    assert frame.width == max(0, width)
    assert frame.height == max(0, height)
    assert len(frame.rows) == max(0, height)

    for row in frame.rows:
        assert len(row) == max(0, width)
        for cell in row:
            assert isinstance(cell, Cell)
            assert len(cell.character) == 1
            assert cell.character.isprintable() or cell.character == " "


def test_horizon_animation_progression():
    """HorizonScene advances cloud positions and water wave phase over time."""
    scene = HorizonScene(seed=42)
    scene.on_enter()

    frame1 = scene.render(80, 24)
    # Simulate 1.5 seconds of time
    for _ in range(15):
        scene.update(0.1)
    frame2 = scene.render(80, 24)

    # The frames should not be identical due to cloud movement and wave ripple phase
    diffs = 0
    for y in range(24):
        for x in range(80):
            if frame1.rows[y][x] != frame2.rows[y][x]:
                diffs += 1
    assert diffs > 0


def test_horizon_dt_handling():
    """HorizonScene gracefully handles zero, negative, and large dt values."""
    scene = HorizonScene(seed=42)
    scene.on_enter()

    # Zero and negative dt do not raise or jump
    scene.update(0.0)
    scene.update(-1.0)
    assert scene._time == 0.0

    # Large dt is clamped
    scene.update(100.0)
    assert scene._time <= 0.5


def test_horizon_seed_reproducibility():
    """Horizon scenes initialized with the same seed generate identical frames."""
    s1 = HorizonScene(seed=99)
    s2 = HorizonScene(seed=99)

    s1.on_enter()
    s2.on_enter()

    f1 = s1.render(80, 24)
    f2 = s2.render(80, 24)

    assert f1.rows == f2.rows
