"""Tests for low-level MpvEngine."""

import asyncio
import json

import pytest

from muzo.player.engine import MpvEngine
from muzo.player.models import MpvIPCError, MpvNotInstalledError


def test_missing_mpv_binary_raises():
    """Engine raises MpvNotInstalledError when binary is not found."""
    engine = MpvEngine(mpv_path="/path/that/does/not/exist/mpv")
    with pytest.raises(MpvNotInstalledError, match="mpv is not installed"):
        engine._resolve_mpv_binary()


@pytest.mark.asyncio
async def test_command_matching_and_events():
    """Engine correctly routes request_id responses and dispatches incoming events."""
    engine = MpvEngine(volume=70)
    # Simulate a fake running state with an in-memory stream pair
    events_received: list[tuple[str, dict]] = []
    engine._event_callback = lambda ev, data: events_received.append((ev, data))

    # Create dummy reader/writer simulation
    reader = asyncio.StreamReader()

    # Mock writer
    class DummyWriter:
        def __init__(self):
            self.written: list[bytes] = []

        def write(self, data: bytes):
            self.written.append(data)

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    writer = DummyWriter()
    engine._reader = reader
    engine._writer = writer  # type: ignore[assignment]
    engine._process = type("Process", (), {"returncode": None})()  # type: ignore[assignment]
    # start background reader

    reader_task = asyncio.create_task(engine._ipc_reader_loop())
    engine._reader_task = reader_task

    # Send command asynchronously
    cmd_task = asyncio.create_task(engine.send_command(["get_property", "pause"]))

    # Wait briefly for command to be written
    await asyncio.sleep(0.02)
    assert len(writer.written) == 1
    sent_json = json.loads(writer.written[0].decode("utf-8"))
    req_id = sent_json["request_id"]
    assert sent_json["command"] == ["get_property", "pause"]

    # Feed an event first, then the command reply into the reader
    reader.feed_data(b'{"event": "file-loaded"}\n')
    reader.feed_data(f'{{"request_id": {req_id}, "data": false, "error": "success"}}\n'.encode())

    reply = await cmd_task
    assert reply["data"] is False
    assert reply["error"] == "success"
    assert len(events_received) == 1
    assert events_received[0][0] == "file-loaded"

    # Clean up
    reader_task.cancel()
    try:
        await reader_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_send_command_not_running_raises():
    """Attempting to send commands when engine is not active raises MpvIPCError."""
    engine = MpvEngine()
    with pytest.raises(MpvIPCError, match="not running"):
        await engine.send_command(["stop"])
