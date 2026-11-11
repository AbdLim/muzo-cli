# muzo 📻

An ambient internet radio player for your terminal.

Pair chill lofi and ambient streaming stations with cozy procedural ASCII art worlds right in your shell.

<!-- TODO: add a demo GIF / asciinema recording here -->

## Install

```bash
# Install as a tool straight from GitHub (needs uv: https://docs.astral.sh/uv/)
uv tool install git+https://github.com/AbdLim/muzo-cli

muzo
```

Or run from a clone:

```bash
git clone https://github.com/AbdLim/muzo-cli && cd muzo-cli
uv run muzo
```

### Requirements

- macOS or Linux (Windows is not supported yet)
- Python >= 3.12
- [mpv](https://mpv.io) (for live audio playback)
  - macOS: `brew install mpv`
  - Ubuntu/Debian: `sudo apt install mpv`
  - Arch Linux: `sudo pacman -S mpv`

### Controls

- `r` — Browse & select radio stations
- `s` — Switch ambient visual worlds
- `f` — Toggle full-screen focus mode
- `Space` — Toggle pause / resume stream (or play the remembered station)
- `x` — Stop playback
- `+` / `-` — Volume up / down
- `?` — Toggle help overlay
- `q` — Quit

### Ambient Worlds

Muzo features four procedurally animated worlds:
- **Rainy Window** — A quiet nighttime city skyline under falling raindrops.
- **Endless Horizon** — A warm, slow sunset over gentle ocean waves.
- **Stargazing** — Serene mountain silhouettes under twinkling stars and occasional shooting stars.
- **Fireplace** — A cozy crackling brick hearth with dancing flames and rising embers.

Switch worlds with `s`, or start in one with `muzo --scene fireplace`
(ids: `rainy-window`, `horizon`, `stargazing`, `fireplace`).

### Command line

```
muzo [-c PATH] [-s SCENE] [-f] [-v]

  -c, --config PATH   Use an explicit TOML config file
  -s, --scene SCENE   Start in the given world
  -f, --focus         Start in full-screen focus mode
  -v, --version       Show version
```

### Configuration

muzo reads an optional TOML file, and updates it when you change world, toggle focus mode or pick
a station. It remembers your last station: on launch press `Space` to play it, or set
`autoplay = true` to start it automatically.

- macOS: `~/Library/Application Support/muzo/config.toml`
- Linux: `~/.config/muzo/config.toml`

```toml
scene = "rainy-window"   # rainy-window | horizon | stargazing | fireplace
volume = 70              # 0-100
animation_fps = 10       # 1-30
focus_mode = false
reduce_motion = false    # calmer, less animated scenes
autoplay = false         # start the last station automatically on launch
# station = "<id>"      # last station; set automatically when you pick one
```

### Notes

Radio stations are discovered via the community [Radio Browser](https://www.radio-browser.info/)
directory, with automatic fallback between its mirror servers. Audio is played by `mpv`.

## Development

```bash
uv sync --all-groups
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## License

[MIT](LICENSE)
