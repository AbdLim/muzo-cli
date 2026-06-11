"""Tests for Muzo configuration loading and validation."""

import pytest

from muzo.config import AppConfig, ConfigError, load_config


def test_missing_implicit_config_yields_defaults(tmp_path, monkeypatch):
    """When no config file exists at the default path, default AppConfig is returned."""
    fake_default = tmp_path / "default_config.toml"
    monkeypatch.setattr("muzo.config.get_default_config_path", lambda: fake_default)

    config = load_config()
    assert config == AppConfig()
    assert config.scene == "welcome"
    assert config.volume == 70
    assert config.animation_fps == 10
    assert config.show_controls is True


def test_valid_toml_overrides_defaults(tmp_path):
    """A valid TOML config file overrides default values."""
    cfg = tmp_path / "custom.toml"
    cfg.write_text(
        """
scene = "welcome"
volume = 85
animation_fps = 15
show_controls = false
station = "lofi-beats"
"""
    )

    config = load_config(cfg, explicit=True)
    assert config.scene == "welcome"
    assert config.volume == 85
    assert config.animation_fps == 15
    assert config.show_controls is False
    assert config.station == "lofi-beats"


def test_invalid_toml_syntax_yields_readable_error(tmp_path):
    """Malformed TOML syntax raises a descriptive ConfigError."""
    cfg = tmp_path / "bad_syntax.toml"
    cfg.write_text("volume = [unclosed bracket")

    with pytest.raises(ConfigError, match="Malformed TOML"):
        load_config(cfg, explicit=True)


def test_volume_out_of_range(tmp_path):
    """Volume values outside [0, 100] raise ConfigError."""
    cfg = tmp_path / "bad_vol.toml"
    cfg.write_text("volume = 120\n")

    with pytest.raises(ConfigError, match="volume.*between 0 and 100"):
        load_config(cfg, explicit=True)

    cfg.write_text("volume = -1\n")
    with pytest.raises(ConfigError, match="volume.*between 0 and 100"):
        load_config(cfg, explicit=True)


def test_volume_boolean_rejected(tmp_path):
    """Boolean values for volume (which in Python subclass int) must be rejected."""
    cfg = tmp_path / "bool_vol.toml"
    cfg.write_text("volume = true\n")

    with pytest.raises(ConfigError, match="volume.*integer"):
        load_config(cfg, explicit=True)


def test_animation_fps_out_of_range_or_bool(tmp_path):
    """FPS outside [1, 30] or boolean values raise ConfigError."""
    cfg = tmp_path / "bad_fps.toml"

    cfg.write_text("animation_fps = 0\n")
    with pytest.raises(ConfigError, match="animation_fps.*between 1 and 30"):
        load_config(cfg, explicit=True)

    cfg.write_text("animation_fps = 60\n")
    with pytest.raises(ConfigError, match="animation_fps.*between 1 and 30"):
        load_config(cfg, explicit=True)

    cfg.write_text("animation_fps = true\n")
    with pytest.raises(ConfigError, match="animation_fps.*integer"):
        load_config(cfg, explicit=True)


def test_scene_empty_or_wrong_type(tmp_path):
    """Non-string or empty string scene values raise ConfigError."""
    cfg = tmp_path / "bad_scene.toml"

    cfg.write_text("scene = ''\n")
    with pytest.raises(ConfigError, match="scene.*non-empty string"):
        load_config(cfg, explicit=True)

    cfg.write_text("scene = 42\n")
    with pytest.raises(ConfigError, match="scene.*non-empty string"):
        load_config(cfg, explicit=True)


def test_unrecognized_keys_rejected(tmp_path):
    cfg = tmp_path / "typo.toml"
    cfg.write_text("volumee = 50\nunknown_opt = true\n")
    pattern = r"Unknown configuration key\(s\):.*unknown_opt.*volumee"
    with pytest.raises(ConfigError, match=pattern):
        load_config(cfg, explicit=True)


def test_nonexistent_explicit_path_raises(tmp_path):
    """Passing a nonexistent explicit config file raises ConfigError."""
    missing = tmp_path / "nonexistent.toml"
    with pytest.raises(ConfigError, match="Configuration file not found"):
        load_config(missing, explicit=True)


def test_nonexistent_implicit_path_does_not_raise(tmp_path):
    """A missing default config path does not raise an error."""
    missing = tmp_path / "missing.toml"
    config = load_config(missing, explicit=False)
    assert config == AppConfig()
