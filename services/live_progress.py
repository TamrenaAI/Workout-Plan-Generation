"""
In-memory, per-session progress event bus.

The agent pipeline runs as a background asyncio task (kicked off from
POST /generate-plan) and publishes real progress events here as it goes —
agents/streaming.py translates deepagents' astream_events() output into
these events. The SSE endpoint (GET /generate-plan/stream/{session_id})
reads from the same session's stream and forwards events to the browser.

Single-process, in-memory only — fine for this stage (one FastAPI worker,
no distributed deployment). If this ever needs to survive a worker restart
or run across multiple processes, swap this module for a real broker
(Redis pub/sub, etc.) without touching agents/streaming.py or the route.
"""

import asyncio
from dataclasses import dataclass, field


@dataclass
class SessionStream:
    queue: "asyncio.Queue[dict]" = field(default_factory=asyncio.Queue)
    history: list[dict] = field(default_factory=list)
    done: bool = False
    task: "asyncio.Task | None" = None


_streams: dict[str, SessionStream] = {}


def create_stream(session_id: str) -> SessionStream:
    stream = SessionStream()
    _streams[session_id] = stream
    return stream


def get_stream(session_id: str) -> "SessionStream | None":
    return _streams.get(session_id)


async def publish(session_id: str, event: dict) -> None:
    """Push a progress event. Buffered in `history` too, so a subscriber that
    connects slightly after the background task started still gets everything
    from the beginning, not just events emitted after it joined."""
    stream = _streams.get(session_id)
    if not stream:
        return
    stream.history.append(event)
    await stream.queue.put(event)


async def publish_done(session_id: str, result: dict) -> None:
    stream = _streams.get(session_id)
    if not stream:
        return
    event = {"type": "done", **result}
    stream.history.append(event)
    await stream.queue.put(event)
    stream.done = True


def cleanup(session_id: str) -> None:
    _streams.pop(session_id, None)
