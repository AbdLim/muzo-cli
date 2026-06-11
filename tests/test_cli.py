"""Tests for the Muzo command-line interface."""

import subprocess
import sys

from muzo import __version__
from muzo.cli import main


def test_cli_help(capsys):
    """Test that muzo --help exits 0 and prints usage without entering the TUI."""
    try:
        exit_code = main(["--help"])
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "usage: muzo" in captured.out
    assert "An ambient internet radio experience in your terminal." in captured.out


def test_cli_version(capsys):
    """Test that muzo --version exits 0 and prints version."""
    try:
        exit_code = main(["--version"])
    except SystemExit as exc:
        exit_code = exc.code

    assert exit_code == 0
    captured = capsys.readouterr()
    assert f"muzo {__version__}" in captured.out


def test_cli_python_module_help():
    """Test running python -m muzo --help via subprocess."""
    result = subprocess.run(
        [sys.executable, "-m", "muzo", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage: muzo" in result.stdout


def test_cli_nonexistent_explicit_config(tmp_path, capsys):
    """Test that passing a nonexistent explicit config path exits non-zero with error message."""
    missing = tmp_path / "does_not_exist.toml"
    exit_code = main(["--config", str(missing)])
    assert exit_code != 0

    captured = capsys.readouterr()
    assert "Error: Configuration file not found:" in captured.err


def test_cli_invalid_scene_in_config(tmp_path, capsys):
    """Test that selecting an unregistered scene name in config exits non-zero."""
    cfg = tmp_path / "bad_scene.toml"
    cfg.write_text('scene = "nonexistent-scene"\n')

    exit_code = main(["--config", str(cfg)])
    assert exit_code != 0

    captured = capsys.readouterr()
    assert "Error: Configured scene 'nonexistent-scene' is not registered." in captured.err
