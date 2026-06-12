"""Tests for the SQLite store. Each test runs in its own tmp cwd."""

import datetime as dt

import pytest

from emma import db


@pytest.fixture(autouse=True)
def _fresh_db():
    """conftest already chdir's to tmp_path; ensure the schema exists."""
    db.init_db()


def test_upsert_inserts_new_call():
    db.upsert_call(
        "conv-1",
        contact="Dr Patel",
        email="jane@surgery.nhs.uk",
        outcome="meeting_booked",
        score=80,
        tier="HOT",
        score_reasons=["outcome 'meeting_booked': +50", "email captured: +20"],
    )
    call = db.get_call("conv-1")
    assert call is not None
    assert call["contact"] == "Dr Patel"
    assert call["email"] == "jane@surgery.nhs.uk"
    assert call["score"] == 80
    assert call["tier"] == "HOT"
    # JSON field hydrated
    assert isinstance(call["score_reasons"], list)
    assert "email captured: +20" in call["score_reasons"]


def test_upsert_updates_existing_call_without_clobbering_other_columns():
    db.upsert_call("conv-2", contact="Dr Lee", outcome="not_now")
    db.upsert_call("conv-2", email="lee@gp.nhs.uk", score=25, tier="COLD")

    call = db.get_call("conv-2")
    assert call["contact"] == "Dr Lee"          # preserved
    assert call["outcome"] == "not_now"          # preserved
    assert call["email"] == "lee@gp.nhs.uk"      # added
    assert call["tier"] == "COLD"                # added


def test_analysis_field_round_trips_as_json():
    db.upsert_call(
        "conv-3", analysis={"transcript_summary": "Booked.", "model": "opus"}
    )
    call = db.get_call("conv-3")
    assert isinstance(call["analysis"], dict)
    assert call["analysis"]["transcript_summary"] == "Booked."


def test_list_calls_filters_and_counts():
    db.upsert_call("a", outcome="meeting_booked", tier="HOT",
                   started_at="2026-05-20T10:00:00+00:00")
    db.upsert_call("b", outcome="not_now", tier="COLD",
                   started_at="2026-05-21T10:00:00+00:00")
    db.upsert_call("c", outcome="meeting_booked", tier="HOT",
                   started_at="2026-05-22T10:00:00+00:00")

    rows, total = db.list_calls(outcome="meeting_booked")
    assert total == 2
    assert [r["conversation_id"] for r in rows] == ["c", "a"]  # newest first

    rows, total = db.list_calls(tier="COLD")
    assert total == 1
    assert rows[0]["conversation_id"] == "b"


def test_list_calls_paginates():
    for i in range(5):
        db.upsert_call(
            f"p{i}", started_at=f"2026-05-{20+i:02d}T10:00:00+00:00"
        )
    rows, total = db.list_calls(limit=2, offset=1)
    assert total == 5
    assert len(rows) == 2


def test_bookings_upsert_and_upcoming():
    future = (
        dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)
    ).isoformat()
    past = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)
    ).isoformat()

    db.upsert_booking(uid="bk1", start=future, attendee_email="a@b.uk")
    db.upsert_booking(uid="bk2", start=past, attendee_email="c@d.uk")

    upcoming = db.list_upcoming_bookings()
    uids = [b["uid"] for b in upcoming]
    assert "bk1" in uids
    assert "bk2" not in uids


def test_metrics_today_returns_zeros_for_empty_db():
    m = db.metrics("today")
    assert m["calls"] == 0
    assert m["contact_capture_pct"] == 0.0
    assert m["booking_rate_pct"] == 0.0


def test_metrics_today_counts_correctly():
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    db.upsert_call("m1", outcome="meeting_booked", email="x@y", duration_s=120,
                   started_at=now)
    db.upsert_call("m2", outcome="not_now", email="", duration_s=30,
                   started_at=now)
    db.upsert_call("m3", outcome="follow_up_scheduled", email="z@y",
                   duration_s=90, started_at=now)

    m = db.metrics("today")
    assert m["calls"] == 3
    # 2 of 3 have email -> 66.7%
    assert m["contact_capture_pct"] == 66.7
    # 1 of 3 booked -> 33.3%
    assert m["booking_rate_pct"] == 33.3
    # avg duration 80s
    assert m["avg_duration_s"] == 80.0
