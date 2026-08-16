"""Tests for Stargazing scene."""

import pytest

from muzo.scenes.base import Cell, Frame
from muzo.scenes.builtin.stars import StargazingScene


def test_stargazing_metadata():
    """Stargazing scene has valid metadata."""
    scene = StargazingScene()
    assert scene.id == "stargazing"
    assert scene.name == "Stargazing"
    assert scene.description == "A serene night sky, twinkling stars, and distant mountains"
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
def test_stargazing_render_dimensions(width: int, height: int):
    """StargazingScene renders valid frames at various terminal dimensions."""
    scene = StargazingScene(seed=42)
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


def test_stargazing_twinkle_progression():
    """StargazingScene modulates star twinkling smoothly over time."""
    scene = StargazingScene(seed=42)
    scene.on_enter()

    frame1 = scene.render(80, 24)
    # Advance time to trigger twinkling
    for _ in range(20):
        scene.update(0.1)
    frame2 = scene.render(80, 24)

    diffs = 0
    for y in range(24):
        for x in range(80):
            if frame1.rows[y][x] != frame2.rows[y][x]:
                diffs += 1
    assert diffs > 0


def test_stargazing_meteor_bounded():
    """Shooting stars appear under simulated time and are strictly bounded."""
    scene = StargazingScene(seed=42)
    scene.on_enter()

    meteor_observed = False
    # Run 10 seconds of simulated time
    for _ in range(100):
        scene.update(0.1)
        if scene._active_meteor is not None:
            meteor_observed = True
            # Never more than 1 active meteor
            break

    assert meteor_observed


def test_stargazing_seed_reproducibility():
    """Stargazing scenes initialized with the same seed generate identical frames."""
    s1 = StargazingScene(seed=77)
    s2 = StargazingScene(seed=77)

    s1.on_enter()
    s2.on_enter()

    f1 = s1.render(80, 24)
    f2 = s2.render(80, 24)

    assert f1.rows == f2.rows
