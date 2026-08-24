"""Tests for Fireplace scene."""

import pytest

from muzo.scenes.base import Cell, Frame
from muzo.scenes.builtin.fireplace import FireplaceScene


def test_fireplace_metadata():
    """Fireplace scene has valid metadata."""
    scene = FireplaceScene()
    assert scene.id == "fireplace"
    assert scene.name == "Fireplace"
    assert scene.description == "A warm, crackling hearth with dancing flames and rising embers"
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
def test_fireplace_render_dimensions(width: int, height: int):
    """FireplaceScene renders valid frames at various terminal dimensions."""
    scene = FireplaceScene(seed=42)
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


def test_fireplace_flame_animation_progression():
    """Fireplace flames flicker and update grid over time."""
    scene = FireplaceScene(seed=42)
    scene.on_enter()

    frame1 = scene.render(80, 24)
    for _ in range(10):
        scene.update(0.1)
    frame2 = scene.render(80, 24)

    diffs = 0
    for y in range(24):
        for x in range(80):
            if frame1.rows[y][x] != frame2.rows[y][x]:
                diffs += 1
    assert diffs > 0


def test_fireplace_embers_capped():
    """Active embers stay strictly capped without unbound accumulation."""
    scene = FireplaceScene(seed=42)
    scene.on_enter()

    for _ in range(100):
        scene.update(0.1)
        assert len(scene._embers) <= 12


def test_fireplace_seed_reproducibility():
    """Fireplace scenes initialized with the same seed generate identical initial frames."""
    s1 = FireplaceScene(seed=55)
    s2 = FireplaceScene(seed=55)

    s1.on_enter()
    s2.on_enter()

    f1 = s1.render(80, 24)
    f2 = s2.render(80, 24)

    assert f1.rows == f2.rows
