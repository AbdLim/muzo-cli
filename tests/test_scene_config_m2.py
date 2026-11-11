"""Tests for M2 configuration persistence and focus/motion fields."""

from pathlib import Path

import pytest

from muzo.config import AppConfig, ConfigError, load_config, save_config


def test_config_defaults_include_m2_fields():
    """Default AppConfig has focus_mode=False and reduce_motion=False."""
    config = AppConfig()
    assert config.focus_mode is False
    assert config.reduce_motion is False


def test_save_and_load_config_roundtrip(tmp_path: Path):
    """Saving config persists all fields and reloads accurately."""
    config_file = tmp_path / "config.toml"
    cfg = AppConfig(
        scene="stargazing",
        station="http://example.com/stream",
        volume=85,
        animation_fps=15,
        show_controls=True,
        focus_mode=True,
        reduce_motion=True,
    )
    save_config(cfg, config_file)
    assert config_file.exists()

    loaded = load_config(config_file, explicit=True)
    assert loaded.scene == "stargazing"
    assert loaded.station == "http://example.com/stream"
    assert loaded.volume == 85
    assert loaded.animation_fps == 15
    assert loaded.show_controls is True
    assert loaded.focus_mode is True
    assert loaded.reduce_motion is True


def test_load_config_with_visuals_table(tmp_path: Path):
    """Loading config with [visuals] table successfully flattens keys."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
        [visuals]
        scene = "horizon"
        focus_mode = true
        reduce_motion = false
        """,
        encoding="utf-8",
    )

    loaded = load_config(config_file, explicit=True)
    assert loaded.scene == "horizon"
    assert loaded.focus_mode is True
    assert loaded.reduce_motion is False


def test_save_config_atomic(tmp_path: Path):
    """Saving config writes atomically without leaving leftover temp files."""
    config_file = tmp_path / "config.toml"
    cfg = AppConfig(scene="fireplace", focus_mode=False)
    save_config(cfg, config_file)

    tmp_files = list(tmp_path.glob(".*.tmp"))
    assert len(tmp_files) == 0


def test_invalid_focus_mode_type(tmp_path: Path):
    """Non-boolean focus_mode raises ConfigError."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('scene = "horizon"\nfocus_mode = "yes"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="focus_mode.*must be a boolean"):
        load_config(config_file, explicit=True)


def test_invalid_reduce_motion_type(tmp_path: Path):
    """Non-boolean reduce_motion raises ConfigError."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('scene = "horizon"\nreduce_motion = 1\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="reduce_motion.*must be a boolean"):
        load_config(config_file, explicit=True)


def test_save_config_escapes_special_characters(tmp_path: Path):
    """Quotes and backslashes in values round-trip instead of corrupting the TOML."""
    config_file = tmp_path / "config.toml"
    cfg = AppConfig(scene="rainy-window", station='Radio "Chill" \\ Café')
    save_config(cfg, config_file)
    assert load_config(config_file, explicit=True).station == 'Radio "Chill" \\ Café'
