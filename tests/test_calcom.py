"""Tests for the Cal.com client, with the HTTP layer mocked by respx."""

import httpx
import pytest
import respx

from emma.calcom import CalComClient, CalComError
from emma.config import Settings


def _calcom_settings() -> Settings:
    return Settings(
        _env_file=None,
        calcom_api_key="cal-test-key",
        calcom_event_type_id=4242,
        timezone="Europe/London",
    )


@pytest.mark.asyncio
@respx.mock
async def test_get_available_slots_flattens_dated_response():
    respx.get("https://api.cal.com/v2/slots").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "2026-05-21": [{"start": "2026-05-21T09:00:00Z"}],
                    "2026-05-22": [{"start": "2026-05-22T14:00:00Z"}],
                }
            },
        )
    )
    slots = await CalComClient(_calcom_settings()).get_available_slots()
    assert slots == ["2026-05-21T09:00:00Z", "2026-05-22T14:00:00Z"]


@pytest.mark.asyncio
@respx.mock
async def test_create_booking_returns_the_booking_record():
    route = respx.post("https://api.cal.com/v2/bookings").mock(
        return_value=httpx.Response(
            201, json={"status": "success", "data": {"uid": "bk_123"}}
        )
    )
    booking = await CalComClient(_calcom_settings()).create_booking(
        start_iso="2026-05-21T09:00:00Z",
        attendee_name="Dr Jane Patel",
        attendee_email="jane@surgery.nhs.uk",
        practice_name="Riverside Surgery",
    )
    assert booking["uid"] == "bk_123"
    sent = route.calls.last.request
    assert b"eventTypeId" in sent.content


@pytest.mark.asyncio
@respx.mock
async def test_http_error_is_wrapped_in_calcom_error():
    respx.get("https://api.cal.com/v2/slots").mock(
        return_value=httpx.Response(403, text="forbidden")
    )
    with pytest.raises(CalComError):
        await CalComClient(_calcom_settings()).get_available_slots()
