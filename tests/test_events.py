"""Tests for the SSE pub/sub hub and the /api/events endpoint."""

import asyncio

import pytest

from emma.events import Event, Hub, format_sse
from emma.server import app


@pytest.mark.asyncio
async def test_hub_publish_reaches_one_subscriber():
    h = Hub()
    q = await h.subscribe()
    h.publish("call_updated", conversation_id="c1", tier="HOT")
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event.type == "call_updated"
    assert event.data == {"conversation_id": "c1", "tier": "HOT"}


@pytest.mark.asyncio
async def test_hub_unsubscribe_stops_delivery():
    h = Hub()
    q = await h.subscribe()
    await h.unsubscribe(q)
    h.publish("call_updated", x=1)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_hub_fans_out_to_every_subscriber():
    h = Hub()
    q1 = await h.subscribe()
    q2 = await h.subscribe()
    h.publish("ping")
    e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert e1.type == "ping"
    assert e2.type == "ping"


@pytest.mark.asyncio
async def test_hub_publish_drops_silently_when_a_queue_is_full():
    h = Hub()
    q = await h.subscribe()
    for _ in range(200):
        try:
            q.put_nowait(Event(type="x"))
        except asyncio.QueueFull:
            break
    # Must not raise even when the subscriber's queue is at capacity.
    h.publish("overflow")


def test_format_sse_renders_a_well_formed_frame():
    frame = format_sse(Event(type="call_updated", data={"x": 1}))
    assert frame.startswith("event: call_updated\n")
    assert '"x": 1' in frame
    assert frame.endswith("\n\n")


def test_events_route_is_registered_on_the_app():
    """End-to-end streaming gets exercised in the live demo. Here we only
    assert the route is wired so a refactor cannot silently drop it -
    the synchronous TestClient deadlocks on real SSE streams."""
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/events" in paths
