"""FastAPI router for the Emma dashboard JSON API.

Mounted under `/api`. Optional bearer-token auth via the `DASHBOARD_TOKEN`
env var: empty (default) = open (matches the "no auth for v1" pick), set
= enforced via `Authorization: Bearer <token>`.

Every endpoint returns the empty-state envelope
    {"data": ..., "meta": {...}}
so the frontend never has to guard for `None`.
"""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from emma import db
from emma.config import Settings, get_settings
from emma.events import Event, format_sse, hub

router = APIRouter(prefix="/api", tags=["dashboard"])

_bearer = HTTPBearer(auto_error=False)


def _verify_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    """Bearer-token gate. No-op when DASHBOARD_TOKEN is empty."""
    token = settings.dashboard_token
    if not token:
        return
    if creds is None or creds.credentials != token:
        raise HTTPException(status_code=401, detail="invalid token")


# --- Calls --------------------------------------------------------------
@router.get("/calls", dependencies=[Depends(_verify_token)])
def list_calls_endpoint(
    limit: int = 50,
    offset: int = 0,
    outcome: str | None = None,
    tier: str | None = None,
    from_iso: str | None = None,
    to_iso: str | None = None,
) -> dict[str, Any]:
    rows, total = db.list_calls(
        limit=limit,
        offset=offset,
        outcome=outcome,
        tier=tier,
        from_iso=from_iso,
        to_iso=to_iso,
    )
    return {
        "data": rows,
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.get("/calls/{conversation_id}", dependencies=[Depends(_verify_token)])
def get_call_endpoint(conversation_id: str) -> dict[str, Any]:
    row = db.get_call(conversation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="call not found")
    return {"data": row}


# --- Leads --------------------------------------------------------------
@router.get("/leads", dependencies=[Depends(_verify_token)])
def list_leads_endpoint() -> dict[str, Any]:
    grouped = db.list_leads_by_tier()
    return {
        "data": grouped,
        "meta": {tier: len(rows) for tier, rows in grouped.items()},
    }


# --- Action queue (HOT/WARM with email, no booking yet) -----------------
@router.get("/action-queue", dependencies=[Depends(_verify_token)])
def list_action_queue_endpoint(limit: int = 50) -> dict[str, Any]:
    rows = db.list_action_queue(limit=limit)
    return {"data": rows, "meta": {"total": len(rows)}}


# --- Bookings -----------------------------------------------------------
@router.get("/bookings/upcoming", dependencies=[Depends(_verify_token)])
def list_bookings_upcoming_endpoint(limit: int = 20) -> dict[str, Any]:
    rows = db.list_upcoming_bookings(limit=limit)
    return {"data": rows, "meta": {"total": len(rows)}}


# --- Metrics ------------------------------------------------------------
@router.get("/metrics", dependencies=[Depends(_verify_token)])
def metrics_endpoint(range: str = "today") -> dict[str, Any]:
    return {"data": db.metrics(range_=range)}


# --- Live events (Server-Sent Events) -----------------------------------
@router.get("/events", dependencies=[Depends(_verify_token)])
async def events_endpoint(request: Request) -> StreamingResponse:
    """Stream live updates so the dashboard can refresh without polling.

    Frame format: standard SSE - `event: <type>\\ndata: <json>\\n\\n`.
    A 15s timeout drives a heartbeat comment so proxies (ngrok etc.) do
    not close idle connections.
    """
    queue = await hub.subscribe()

    async def stream() -> AsyncIterator[str]:
        try:
            yield format_sse(Event(type="connected", data={"ok": True}))
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield format_sse(event)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            await hub.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")
