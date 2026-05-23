"""Configuration management for Muzo."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_config_path


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


@dataclass(frozen=True, slots=True)
class AppConfig:
    scene: str = "welcome"
    station: str | None = None
    volume: int = 70
    animation_fps: int = 10
    show_controls: bool = True


_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"scene", "station", "volume", "animation_fps", "show_controls"}
)


def get_default_config_path() -> Path:
    """Return the platform-specific default configuration file path."""
    return user_config_path("muzo") / "config.toml"


def validate_config_dict(data: dict[str, Any]) -> None:
    """Validate raw configuration values from parsed TOML."""
    # No stowaways allowed on the Going Merry — catch typos early
    unknown = set(data.keys()) - _ALLOWED_KEYS
    if unknown:
        keys_str = ", ".join(sorted(unknown))
        raise ConfigError(f"Unknown configuration key(s): {keys_str}")

    if "scene" in data:
        scene = data["scene"]
        if not isinstance(scene, str) or not scene.strip():
            raise ConfigError("Configuration key 'scene' must be a non-empty string.")

    if "station" in data:
        station = data["station"]
        if station is not None and (not isinstance(station, str) or not station.strip()):
            raise ConfigError("Configuration key 'station' must be null or a non-empty string.")

    if "volume" in data:
        volume = data["volume"]
        # In Python, isinstance(True, int) is True because history is weird.
        # Don't let someone set volume = True and wonder why it's at 1%.
        if isinstance(volume, bool) or not isinstance(volume, int):
            raise ConfigError("Configuration key 'volume' must be an integer between 0 and 100.")
        if not (0 <= volume <= 100):
            raise ConfigError(
                f"Configuration key 'volume' must be between 0 and 100, got {volume}."
            )

    if "animation_fps" in data:
        fps = data["animation_fps"]
        if isinstance(fps, bool) or not isinstance(fps, int):
            raise ConfigError(
                "Configuration key 'animation_fps' must be an integer between 1 and 30."
            )
        if not (1 <= fps <= 30):
            raise ConfigError(
                f"Configuration key 'animation_fps' must be between 1 and 30, got {fps}."
            )

    if "show_controls" in data:
        show_controls = data["show_controls"]
        if not isinstance(show_controls, bool):
            raise ConfigError("Configuration key 'show_controls' must be a boolean.")


def load_config(path: Path | None = None, explicit: bool = False) -> AppConfig:
    """Load and validate configuration from the specified path or platform default.

    Args:
        path: Optional path to config file.
        explicit: If True, failing to find or open the file is an error.
                 If False, a missing default config cleanly yields defaults.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigError: On unreadable file, malformed TOML, or invalid config values.
    """
    config_path = path or get_default_config_path()

    if not config_path.exists():
        if explicit:
            raise ConfigError(f"Configuration file not found: {config_path}")
        return AppConfig()

    if not config_path.is_file():
        raise ConfigError(f"Configuration path is not a file: {config_path}")

    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError as err:
        raise ConfigError(f"Could not read configuration file '{config_path}': {err}") from err

    try:
        raw_data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as err:
        raise ConfigError(f"Malformed TOML in '{config_path}': {err}") from err

    if not isinstance(raw_data, dict):
        raise ConfigError(
            f"Configuration file root must be a TOML table, got {type(raw_data).__name__}."
        )

    validate_config_dict(raw_data)
    return AppConfig(**raw_data)
