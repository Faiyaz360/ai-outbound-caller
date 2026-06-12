"""Tests for Emma's tool schemas and dispatch handlers."""

import datetime as dt
import json
from pathlib import Path

import pytest

from emma.tools import _fallback_slots, elevenlabs_tool_configs, handle_tool_call


def test_tool_configs_expose_three_webhook_tools(settings):
    configs = elevenlabs_tool_configs(settings)
    names = {c["name"] for c in configs}
    assert names == {"check_availability", "book_meeting", "log_call_outcome"}
    assert all(c["type"] == "webhook" for c in configs)


def test_tool_configs_point_at_the_server_with_a_secret_header(settings):
    for config in elevenlabs_tool_configs(settings):
        schema = config["api_schema"]
        assert schema["method"] == "POST"
        assert schema["url"].startswith("https://example.test/tools/")
        assert schema["request_headers"]["x-emma-tool-secret"] == "test-secret"


def test_fallback_slots_are_weekday_iso_times(settings):
    slots = _fallback_slots(settings)
    assert len(slots) == 6
    for iso in slots:
        moment = dt.datetime.fromisoformat(iso)
        assert moment.weekday() < 5  # Monday-Friday only


@pytest.mark.asyncio
async def test_check_availability_falls_back_without_calcom(settings):
    result = await handle_tool_call("check_availability", {}, settings)
    assert "Open meeting slots" in result
    assert "start_iso:" in result


@pytest.mark.asyncio
async def test_book_meeting_rejects_incomplete_details(settings):
    result = await handle_tool_call(
        "book_meeting", {"start_iso": "2026-05-21T09:00:00+00:00"}, settings
    )
    assert "still need" in result.lower()


@pytest.mark.asyncio
async def test_book_meeting_provisional_logs_the_booking(settings):
    result = await handle_tool_call(
        "book_meeting",
        {
            "start_iso": "2026-05-21T09:00:00+00:00",
            "attendee_name": "Dr Jane Patel",
            "attendee_email": "jane@surgery.nhs.uk",
            "practice_name": "Riverside Surgery",
        },
        settings,
    )
    assert "provisionally booked" in result.lower()
    logged = Path("call_log.jsonl").read_text(encoding="utf-8")
    assert "booking_provisional" in logged


@pytest.mark.asyncio
async def test_log_call_outcome_captures_outcome_and_email(settings):
    result = await handle_tool_call(
        "log_call_outcome",
        {
            "outcome": "not_now",
            "summary": "Not ready - wants a demo video first.",
            "email": "jane@surgery.nhs.uk",
        },
        settings,
    )
    assert "recorded" in result.lower()
    record = json.loads(Path("call_log.jsonl").read_text(encoding="utf-8").strip())
    assert record["outcome"] == "not_now"
    assert record["email"] == "jane@surgery.nhs.uk"


@pytest.mark.asyncio
async def test_unknown_tool_is_handled_gracefully(settings):
    result = await handle_tool_call("teleport", {}, settings)
    assert "Unknown tool" in result


@pytest.mark.asyncio
async def test_log_call_outcome_with_conversation_id_persists_to_db(settings):
    from emma import db

    result = await handle_tool_call(
        "log_call_outcome",
        {"outcome": "meeting_booked", "summary": "Booked.", "email": "x@y.uk"},
        settings,
        conversation_id="conv-xyz",
    )
    assert "recorded" in result.lower()
    row = db.get_call("conv-xyz")
    assert row is not None
    assert row["outcome"] == "meeting_booked"
    assert row["email"] == "x@y.uk"
    # 50 (outcome) + 20 (email) = 70 -> HOT
    assert row["score"] == 70
    assert row["tier"] == "HOT"


@pytest.mark.asyncio
async def test_log_call_outcome_without_conversation_id_skips_db(settings):
    from emma import db

    await handle_tool_call(
        "log_call_outcome",
        {"outcome": "not_now", "summary": "no."},
        settings,
    )
    # No conversation id -> no DB row (the JSONL append still happened).
    assert db.get_call("any-id") is None


@pytest.mark.asyncio
async def test_book_meeting_with_conversation_id_persists_booking_and_call(settings):
    from emma import db

    result = await handle_tool_call(
        "book_meeting",
        {
            # Pinned far-future date so list_upcoming_bookings always finds it,
            # regardless of when the test suite runs.
            "start_iso": "2099-05-21T09:00:00+00:00",
            "attendee_name": "Dr Jane Patel",
            "attendee_email": "jane@surgery.nhs.uk",
            "practice_name": "Riverside Surgery",
        },
        settings,
        conversation_id="conv-book",
    )
    assert "provisionally booked" in result.lower()

    call = db.get_call("conv-book")
    assert call is not None
    assert call["outcome"] == "meeting_booked"
    assert call["email"] == "jane@surgery.nhs.uk"
    assert call["tier"] == "HOT"

    bookings = db.list_upcoming_bookings()
    assert any(
        b["attendee_email"] == "jane@surgery.nhs.uk" for b in bookings
    )
