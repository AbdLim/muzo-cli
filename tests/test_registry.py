"""Tests for scene base contracts, built-in welcome scene, and scene registry."""

import pytest

from muzo.scenes.base import Cell, Frame, Scene
from muzo.scenes.builtin.welcome import WelcomeScene
from muzo.scenes.registry import (
    DuplicateSceneError,
    SceneNotFoundError,
    SceneRegistry,
    create_default_registry,
)


def test_builtin_welcome_scene_registers_and_instantiates():
    """WelcomeScene registers in default registry and instantiates correctly."""
    registry = create_default_registry()
    assert registry.is_registered("welcome")

    scene_cls = registry.get("welcome")
    assert scene_cls is WelcomeScene

    scene = registry.create("welcome")
    assert isinstance(scene, WelcomeScene)
    assert scene.id == "welcome"
    assert scene.name == "Welcome"


def test_registry_duplicate_id_fails():
    """Registering two scenes with the same ID raises DuplicateSceneError."""
    registry = SceneRegistry()

    class FirstScene(Scene):
        id = "duplicate-test"
        name = "First"
        description = "First test scene"

        def render(self, width: int, height: int) -> Frame:
            return Frame.empty(width, height)

    class SecondScene(Scene):
        id = "duplicate-test"
        name = "Second"
        description = "Second test scene"

        def render(self, width: int, height: int) -> Frame:
            return Frame.empty(width, height)

    registry.register(FirstScene)
    with pytest.raises(DuplicateSceneError, match="already registered"):
        registry.register(SecondScene)


def test_registry_invalid_id_fails():
    """Scene IDs must be ASCII lowercase kebab-case."""
    registry = SceneRegistry()

    invalid_ids = [
        "UpperScene",
        "under_score",
        "has space",
        "",
        "-starts-with-dash",
        "ends-with-dash-",
        "special!chars",
    ]

    for bad_id in invalid_ids:

        class BadScene(Scene):
            id = bad_id
            name = "Test"
            description = "Test description"

            def render(self, width: int, height: int) -> Frame:
                return Frame.empty(width, height)

        with pytest.raises(ValueError, match="kebab-case"):
            registry.register(BadScene)


def test_registry_unknown_scene_fails():
    """Requesting an unregistered scene ID raises SceneNotFoundError."""
    registry = SceneRegistry()
    with pytest.raises(SceneNotFoundError, match="Unknown scene ID"):
        registry.get("nonexistent-scene")

    with pytest.raises(SceneNotFoundError, match="Unknown scene ID"):
        registry.create("nonexistent-scene")


def test_registry_listing_sorted():
    """Registered scenes are listed deterministically sorted by ID."""
    registry = SceneRegistry()

    class BetaScene(Scene):
        id = "beta-scene"
        name = "Beta"
        description = "Beta description"

        def render(self, width: int, height: int) -> Frame:
            return Frame.empty(width, height)

    class AlphaScene(Scene):
        id = "alpha-scene"
        name = "Alpha"
        description = "Alpha description"

        def render(self, width: int, height: int) -> Frame:
            return Frame.empty(width, height)

    registry.register(BetaScene)
    registry.register(AlphaScene)

    listing = registry.list_scenes()
    assert len(listing) == 2
    assert listing[0].id == "alpha-scene"
    assert listing[1].id == "beta-scene"


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (80, 24),
        (40, 12),
        (1, 1),
        (0, 0),
        (25, 5),
    ],
)
def test_welcome_scene_render_dimensions(width, height):
    """WelcomeScene renders valid Frames at various terminal dimensions without crashing."""
    scene = WelcomeScene()
    frame = scene.render(width, height)

    assert frame.width == width
    assert frame.height == height
    assert len(frame.rows) == height
    for row in frame.rows:
        assert len(row) == width
        for cell in row:
            assert isinstance(cell, Cell)


def test_frame_invariants():
    """Frame validates dimension constraints and cell contents."""
    # Negative dimensions
    with pytest.raises(ValueError, match="non-negative"):
        Frame(width=-1, height=10, rows=())

    with pytest.raises(ValueError, match="non-negative"):
        Frame(width=10, height=-1, rows=())

    # Row count mismatch
    with pytest.raises(ValueError, match="row count"):
        Frame(width=2, height=2, rows=((Cell(), Cell()),))

    # Row width mismatch
    with pytest.raises(ValueError, match="width"):
        Frame(width=2, height=1, rows=((Cell(),),))

    # Invalid element type
    with pytest.raises(TypeError, match="Expected Cell"):
        Frame(width=1, height=1, rows=(("not a cell",),))  # type: ignore


def test_cell_invariants():
    """Cell enforces exactly 1 character and printable characters."""
    # Length != 1
    with pytest.raises(ValueError, match="exactly 1 character"):
        Cell(character="")

    with pytest.raises(ValueError, match="exactly 1 character"):
        Cell(character="ab")

    # Non-printable
    with pytest.raises(ValueError, match="printable"):
        Cell(character="\x00")

    # Valid cells
    c1 = Cell(character=" ")
    assert c1.character == " "
    c2 = Cell(character="x", foreground="#ffffff", background="#000000")
    assert c2.foreground == "#ffffff"
