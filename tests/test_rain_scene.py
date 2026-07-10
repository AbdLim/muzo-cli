"""Tests for the RainyWindowScene."""

import pytest

from muzo.scenes.base import Cell
from muzo.scenes.builtin.rain import RainyWindowScene
from muzo.scenes.builtin.welcome import WelcomeScene
from muzo.scenes.registry import create_default_registry


def test_registry_contains_both_scenes():
    """Default registry registers both rainy-window and welcome scenes."""
    registry = create_default_registry()
    assert registry.is_registered("rainy-window")
    assert registry.is_registered("welcome")
    assert registry.get("rainy-window") is RainyWindowScene
    assert registry.get("welcome") is WelcomeScene


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (80, 24),
        (120, 35),
        (40, 12),
        (20, 8),
        (1, 1),
        (0, 0),
    ],
)
def test_rain_scene_dimensions(width, height):
    """RainyWindowScene renders valid frames across various dimensions."""
    scene = RainyWindowScene(seed=123)
    frame = scene.render(width, height)

    assert frame.width == width
    assert frame.height == height
    assert len(frame.rows) == height
    for row in frame.rows:
        assert len(row) == width
        for cell in row:
            assert isinstance(cell, Cell)
            assert len(cell.character) == 1


def test_deterministic_rendering():
    """Identical seed and sequence of dt yields identical frames."""
    s1 = RainyWindowScene(seed=777)
    s2 = RainyWindowScene(seed=777)

    f1_initial = s1.render(80, 24)
    f2_initial = s2.render(80, 24)
    assert f1_initial.rows == f2_initial.rows

    s1.update(0.1)
    s2.update(0.1)

    f1_next = s1.render(80, 24)
    f2_next = s2.render(80, 24)
    assert f1_next.rows == f2_next.rows


def test_update_dt_advancement_and_clamping():
    """update(0) does not advance state, valid dt produces movement, and large dt is clamped."""
    scene = RainyWindowScene(seed=42)
    scene.render(80, 24)

    initial_positions = [p["y"] for p in scene._particles]

    # dt <= 0 should produce no change
    scene.update(0.0)
    assert [p["y"] for p in scene._particles] == initial_positions

    scene.update(-1.0)
    assert [p["y"] for p in scene._particles] == initial_positions

    # dt > 0 advances positions
    scene.update(0.05)
    advanced_positions = [p["y"] for p in scene._particles]
    assert advanced_positions != initial_positions

    # Large dt is clamped without raising exceptions
    scene.update(100.0)
    for p in scene._particles:
        assert -5.0 <= p["y"] <= 25.0
