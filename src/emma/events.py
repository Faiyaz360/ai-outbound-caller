"""In-process pub/sub for the SSE event stream.

A Hub keeps per-subscriber `asyncio.Queue` instances. Synchronous callers
(tool handlers) and async callers (post-call webhook) alike can call
`hub.publish(...)` from any FastAPI request handler - they all run on the
event loop's thread, so the underlying `queue.put_nowait` is safe without
extra locks.

If a subscriber's queue fills up (slow consumer), the event is dropped for
that subscriber only; the rest still receive it.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

_MAX_QUEUE_SIZE = 100


@dataclass
class Event:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class Hub:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []

    async def subscribe(self) -> "asyncio.Queue[Event]":
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: "asyncio.Queue[Event]") -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, event_type: str, **data: Any) -> None:
        """Non-blocking broadcast. Drops to any subscriber whose queue is full."""
        event = Event(type=event_type, data=data)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


def format_sse(event: Event) -> str:
    """Render one SSE frame: `event: <type>\\ndata: <json>\\n\\n`."""
    payload = json.dumps(event.data, default=str)
    return f"event: {event.type}\ndata: {payload}\n\n"


# Module-level singleton used by the rest of the app.
hub = Hub()
