"""Tests for M2 scene registry and listing."""

from muzo.scenes.registry import create_default_registry


def test_default_registry_contains_all_four_ambient_scenes():
    """Default registry contains rainy-window, horizon, stargazing, and fireplace."""
    registry = create_default_registry()

    expected_ambient = ["rainy-window", "horizon", "stargazing", "fireplace"]
    for scene_id in expected_ambient:
        assert registry.is_registered(scene_id)
        scene_type = registry.get(scene_id)
        assert scene_type.id == scene_id
        assert getattr(scene_type, "is_ambient", True) is True


def test_list_ambient_scenes_order():
    """list_ambient_scenes returns the curated presentation order."""
    registry = create_default_registry()
    ambient = registry.list_ambient_scenes()

    ids = [info.id for info in ambient]
    assert ids == ["rainy-window", "horizon", "stargazing", "fireplace"]


def test_welcome_scene_preserved_but_not_ambient():
    """Legacy welcome scene is retained in registry but excluded from ambient listing."""
    registry = create_default_registry()
    assert registry.is_registered("welcome")

    ambient_ids = [info.id for info in registry.list_ambient_scenes()]
    assert "welcome" not in ambient_ids

    all_ids = [info.id for info in registry.list_scenes()]
    assert "welcome" in all_ids
