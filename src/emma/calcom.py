"""Thin async client for the Cal.com v2 API (slot lookup + booking)."""

import datetime as dt
from typing import Any

import httpx

from emma.config import Settings

_BASE_URL = "https://api.cal.com/v2"
_SLOTS_API_VERSION = "2024-09-04"
_BOOKINGS_API_VERSION = "2024-08-13"
_TIMEOUT = 20.0


class CalComError(RuntimeError):
    """Raised when Cal.com returns an error or unexpected response."""


class CalComClient:
    """Wraps the two Cal.com calls Emma needs: availability and booking.

    Pass an httpx.AsyncClient via `client` in tests; in production each
    call opens and closes its own short-lived client.
    """

    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client

    def _headers(self, api_version: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.calcom_api_key}",
            "cal-api-version": api_version,
            "Content-Type": "application/json",
        }

    async def _send(
        self,
        method: str,
        path: str,
        api_version: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = _BASE_URL + path
        headers = self._headers(api_version)
        try:
            if self._client is not None:
                resp = await self._client.request(
                    method, url, headers=headers, params=params, json=json
                )
            else:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.request(
                        method, url, headers=headers, params=params, json=json
                    )
        except httpx.HTTPError as exc:
            raise CalComError(f"Cal.com request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise CalComError(
                f"Cal.com {method} {path} -> {resp.status_code}: {resp.text}"
            )
        return resp.json()

    async def get_available_slots(
        self, *, days_ahead: int = 7, limit: int = 6
    ) -> list[str]:
        """Return up to `limit` open slot start times as ISO-8601 strings."""
        now = dt.datetime.now(dt.timezone.utc)
        params = {
            "eventTypeId": self._settings.calcom_event_type_id,
            "start": now.date().isoformat(),
            "end": (now + dt.timedelta(days=days_ahead)).date().isoformat(),
            "timeZone": self._settings.timezone,
        }
        data = await self._send("GET", "/slots", _SLOTS_API_VERSION, params=params)
        slots_by_date = data.get("data", {})
        out: list[str] = []
        for date_key in sorted(slots_by_date):
            for slot in slots_by_date[date_key]:
                start = slot.get("start") if isinstance(slot, dict) else slot
                if start:
                    out.append(start)
        return out[:limit]

    async def create_booking(
        self,
        *,
        start_iso: str,
        attendee_name: str,
        attendee_email: str,
        practice_name: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """Create a booking and return the Cal.com booking record."""
        body: dict[str, Any] = {
            "start": start_iso,
            "eventTypeId": self._settings.calcom_event_type_id,
            "attendee": {
                "name": attendee_name,
                "email": attendee_email,
                "timeZone": self._settings.timezone,
                "language": "en",
            },
            "metadata": {
                "practice": practice_name[:480],
                "source": "Emma outbound call",
            },
        }
        if notes:
            body["bookingFieldsResponses"] = {"notes": notes}
        data = await self._send(
            "POST", "/bookings", _BOOKINGS_API_VERSION, json=body
        )
        return data.get("data", data)
