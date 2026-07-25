"""Tests for the Textual MuzoApp and SceneView widget."""

import pytest
from textual.geometry import Size

from muzo.app import HelpScreen, MuzoApp
from muzo.config import AppConfig
from muzo.scenes.base import Frame, Scene
from muzo.scenes.registry import SceneRegistry
from muzo.ui.widgets.scene_view import SceneView


@pytest.mark.asyncio
async def test_app_mount_and_quit():
    """App mounts successfully and 'q' triggers exit."""
    app = MuzoApp()
    async with app.run_test(size=(80, 24)) as pilot:
        assert pilot.app.is_mounted
        scene_view = pilot.app.query_one(SceneView)
        assert scene_view is not None
        assert scene_view.scene is not None
        assert scene_view.scene.id == "rainy-window"

        # Press 'q' to quit

        await pilot.press("q")
        assert pilot.app._exit


@pytest.mark.asyncio
async def test_help_overlay_toggle():
    """Pressing '?' displays HelpScreen, and Escape dismisses it."""
    app = MuzoApp()
    async with app.run_test(size=(80, 24)) as pilot:
        # Help is not shown initially
        assert not isinstance(pilot.app.screen, HelpScreen)

        # Press '?' to open help
        await pilot.press("question_mark")
        assert isinstance(pilot.app.screen, HelpScreen)

        # Press 'Escape' to dismiss help
        await pilot.press("escape")
        assert not isinstance(pilot.app.screen, HelpScreen)

        # Press '?' again to open, then '?' to dismiss
        await pilot.press("question_mark")
        assert isinstance(pilot.app.screen, HelpScreen)
        await pilot.press("question_mark")
        assert not isinstance(pilot.app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_help_screen_quit():
    """Pressing 'q' while HelpScreen is open exits the application."""
    app = MuzoApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("question_mark")
        assert isinstance(pilot.app.screen, HelpScreen)

        await pilot.press("q")
        assert pilot.app._exit


@pytest.mark.asyncio
async def test_small_terminal_resize():
    """App handles resizing to small and large dimensions without raising exceptions."""
    app = MuzoApp()
    async with app.run_test(size=(80, 24)) as pilot:
        # Resize down to 40x12
        await pilot.resize_terminal(40, 12)
        assert pilot.app.size == Size(40, 12)

        # Resize down to tiny 20x8
        await pilot.resize_terminal(20, 8)
        assert pilot.app.size == Size(20, 8)

        # Resize back to standard 80x24
        await pilot.resize_terminal(80, 24)
        assert pilot.app.size == Size(80, 24)


@pytest.mark.asyncio
async def test_scene_view_error_handling():
    """SceneView captures render errors and displays error strip without crashing."""

    class FaultyScene(Scene):
        id = "faulty"
        name = "Faulty"
        description = "Throws an error on render"

        def render(self, width: int, height: int) -> Frame:
            raise RuntimeError("Simulation error in scene render")

    registry = SceneRegistry()
    registry.register(FaultyScene)
    config = AppConfig(scene="faulty")

    app = MuzoApp(config=config, registry=registry)
    async with app.run_test(size=(80, 24)) as pilot:
        scene_view = pilot.app.query_one(SceneView)
        assert scene_view is not None

        # Call render_line at mid-height to verify safe strip generation on error
        mid_y = scene_view.size.height // 2
        strip = scene_view.render_line(mid_y)
        assert strip.cell_length == 80
        # The line contains our error indicator
        assert "Scene error" in strip.text
