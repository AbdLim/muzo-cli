import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from muzo.player.models import (
    MpvIPCError,
    MpvNotInstalledError,
    MpvStartupError,
)

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict[str, Any]], None]


class MpvEngine:
    """Manages an external mpv child process and persistent local JSON IPC connection."""

    def __init__(
        self,
        volume: int = 70,
        event_callback: EventCallback | None = None,
        mpv_path: str | None = None,
    ) -> None:
        self._initial_volume = max(0, min(100, volume))
        self._event_callback = event_callback
        self._custom_mpv_path = mpv_path

        self._process: asyncio.subprocess.Process | None = None
        self._temp_dir: Path | None = None
        self._socket_path: Path | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task[None] | None = None

        self._request_counter = 0
        self._pending_requests: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._is_closing = False

    @property
    def is_running(self) -> bool:
        """True if mpv process and IPC connection are active."""
        return (
            self._process is not None
            and getattr(self._process, "returncode", None) is None
            and self._writer is not None
            and not self._is_closing
        )

    def _resolve_mpv_binary(self) -> str:
        """Locate the mpv executable on the host system."""
        if self._custom_mpv_path:
            p = Path(self._custom_mpv_path)
            if p.exists() or shutil.which(self._custom_mpv_path):
                return self._custom_mpv_path
            raise MpvNotInstalledError(
                f"mpv is not installed or not found at '{self._custom_mpv_path}'."
            )

        path = shutil.which("mpv")
        if not path:
            raise MpvNotInstalledError(
                "mpv is not installed or not found on PATH.\n"
                "To enable live radio streaming, install it:\n"
                "  • macOS: brew install mpv\n"
                "  • Ubuntu/Debian: sudo apt install mpv\n"
                "  • Arch Linux: sudo pacman -S mpv"
            )
        return path

    async def start(self) -> None:
        """Launch the mpv child process and connect to its local IPC socket."""
        async with self._lock:
            if self.is_running:
                return

            self._is_closing = False
            binary = self._resolve_mpv_binary()

            # Create private restricted directory for IPC socket (POSIX 0700)
            raw_tmp = tempfile.mkdtemp(prefix="muzo-mpv-")
            self._temp_dir = Path(raw_tmp)
            os.chmod(self._temp_dir, 0o700)
            self._socket_path = self._temp_dir / "ipc.sock"

            cmd = [
                binary,
                "--no-video",
                "--idle=yes",
                "--force-window=no",
                "--terminal=no",
                "--no-config",
                "--ytdl=no",
                "--network-timeout=10",
                f"--input-ipc-server={self._socket_path}",
                f"--volume={self._initial_volume}",
            ]
            if sys.platform == "darwin":
                cmd.append("--ao=avfoundation,coreaudio")

            try:
                self._process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            except Exception as err:
                await self._cleanup_resources()
                raise MpvStartupError(f"Failed to start mpv process: {err}") from err

            # Poll for socket readiness (bounded timeout 3.0s)
            connected = False
            for _ in range(60):
                if self._process.returncode is not None:
                    code = self._process.returncode
                    await self._cleanup_resources()
                    raise MpvStartupError(f"mpv exited prematurely with status code {code}.")

                if self._socket_path.exists():
                    try:
                        self._reader, self._writer = await asyncio.open_unix_connection(
                            str(self._socket_path)
                        )
                        connected = True
                        break
                    except (OSError, ConnectionRefusedError):
                        pass

                await asyncio.sleep(0.05)

            if not connected or self._reader is None or self._writer is None:
                await self._cleanup_resources()
                raise MpvStartupError("Timed out waiting for mpv IPC socket to become available.")

            self._reader_task = asyncio.create_task(
                self._ipc_reader_loop(),
                name="muzo-mpv-ipc-reader",
            )

            # Observe useful property changes
            await self._observe_properties()

    async def _observe_properties(self) -> None:
        """Register for playback property change notifications."""
        for prop in ("pause", "core-idle", "eof-reached"):
            try:
                await self.send_command(["observe_property", 0, prop])
            except Exception as err:
                logger.debug("Failed observing mpv property '%s': %s", prop, err)

    async def send_command(self, command: list[Any], timeout: float = 3.0) -> dict[str, Any]:
        """Send a JSON IPC command and await the response."""
        if not self.is_running or self._writer is None:
            raise MpvIPCError("mpv IPC engine is not running.")

        self._request_counter += 1
        req_id = self._request_counter
        payload = {"command": command, "request_id": req_id}
        line = json.dumps(payload) + "\n"

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_requests[req_id] = future

        try:
            self._writer.write(line.encode("utf-8"))
            await self._writer.drain()
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as err:
            raise MpvIPCError(f"Timed out awaiting reply for command: {command[0]}") from err
        except OSError as err:
            raise MpvIPCError(f"Socket error communicating with mpv: {err}") from err
        finally:
            self._pending_requests.pop(req_id, None)

    async def loadfile(self, stream_url: str) -> None:
        """Instruct mpv to replace the current playback with a new stream URL."""
        if not self.is_running:
            await self.start()
        reply = await self.send_command(["loadfile", stream_url, "replace"])
        err = reply.get("error")
        if err != "success":
            raise MpvIPCError(f"mpv loadfile failed: {err}")

    async def pause(self) -> None:
        """Pause audio playback."""
        if self.is_running:
            await self.send_command(["set_property", "pause", True])

    async def resume(self) -> None:
        """Resume paused audio playback."""
        if self.is_running:
            await self.send_command(["set_property", "pause", False])

    async def stop(self) -> None:
        """Stop current audio stream."""
        if self.is_running:
            await self.send_command(["stop"])

    async def set_volume(self, volume: int) -> None:
        """Set volume percentage (clamped between 0 and 100)."""
        clamped = max(0, min(100, volume))
        if self.is_running:
            await self.send_command(["set_property", "volume", clamped])

    async def _ipc_reader_loop(self) -> None:
        """Background loop reading and dispatching JSON lines from mpv IPC."""
        if self._reader is None:
            return

        try:
            while not self._is_closing and not self._reader.at_eof():
                line_bytes = await self._reader.readline()
                if not line_bytes:
                    break

                line_str = line_bytes.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    data = json.loads(line_str)
                except Exception:
                    continue

                if "request_id" in data:
                    req_id = data["request_id"]
                    future = self._pending_requests.get(req_id)
                    if future and not future.done():
                        future.set_result(data)

                elif "event" in data:
                    event_name = data["event"]
                    if self._event_callback:
                        try:
                            self._event_callback(event_name, data)
                        except Exception as exc:
                            logger.error("Error in mpv event callback: %s", exc)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("mpv IPC reader loop terminated: %s", exc)

    async def close(self) -> None:
        """Gracefully stop mpv and clean up all resources."""
        async with self._lock:
            if self._is_closing:
                return
            self._is_closing = True

            # Cancel pending commands
            for fut in self._pending_requests.values():
                if not fut.done():
                    fut.cancel()
            self._pending_requests.clear()

            # Attempt graceful quit command
            if self._writer is not None:
                try:
                    self._writer.write(b'{"command": ["quit"]}\n')
                    await self._writer.drain()
                except Exception:
                    pass

            if self._reader_task is not None:
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except (asyncio.CancelledError, Exception):
                    pass
                self._reader_task = None

            if self._writer is not None:
                try:
                    self._writer.close()
                    await self._writer.wait_closed()
                except Exception:
                    pass
                self._writer = None
                self._reader = None

            if self._process is not None:
                if self._process.returncode is None:
                    try:
                        self._process.terminate()
                        await asyncio.wait_for(self._process.wait(), timeout=1.0)
                    except (TimeoutError, Exception):
                        try:
                            self._process.kill()
                            await self._process.wait()
                        except Exception:
                            pass
                self._process = None

            await self._cleanup_resources()

    async def _cleanup_resources(self) -> None:
        """Remove temporary socket file and directory."""
        if self._socket_path and self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except Exception:
                pass
            self._socket_path = None

        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
            self._temp_dir = None
