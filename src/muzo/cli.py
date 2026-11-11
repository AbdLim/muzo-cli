"""Command line interface for Muzo."""

import argparse
import dataclasses
import sys
from pathlib import Path

from muzo import __version__
from muzo.app import MuzoApp
from muzo.config import ConfigError, load_config
from muzo.scenes.registry import create_default_registry


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="muzo",
        description="An ambient internet radio experience in your terminal.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"muzo {__version__}",
        help="Show program's version number and exit.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        metavar="PATH",
        default=None,
        help="Path to an explicit TOML configuration file.",
    )
    parser.add_argument(
        "-s",
        "--scene",
        type=str,
        default=None,
        help="Override active ambient scene ID.",
    )
    parser.add_argument(
        "-f",
        "--focus",
        action="store_true",
        default=False,
        help="Launch directly into full-screen focus mode.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Synchronous entry point for the muzo CLI.

    Args:
        argv: Optional command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Process exit code (0 for success, non-zero for errors).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config, explicit=args.config is not None)
        if args.scene is not None:
            config = dataclasses.replace(config, scene=args.scene)
        if args.focus:
            config = dataclasses.replace(config, focus_mode=True)

        registry = create_default_registry()

        if not registry.is_registered(config.scene):
            available = ", ".join(info.id for info in registry.list_scenes())
            print(
                f"Error: Configured scene '{config.scene}' is not registered. "
                f"Available scenes: {available}",
                file=sys.stderr,
            )
            return 1

        app = MuzoApp(config=config, registry=registry)
        app.run()
        return 0
    except ConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Unexpected error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
