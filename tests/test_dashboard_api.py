"""Tests for the /api/* dashboard JSON endpoints."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from emma import db
from emma.config import get_settings
from emma.server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _open_auth(monkeypatch):
    """Default tests assume the bearer gate is OFF (token unset)."""
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- /api/calls ---------------------------------------------------------
def test_list_calls_empty_returns_envelope():
    response = client.get("/api/calls")
    assert response.status_code == 200
    body = response.json()
    assert body == {"data": [], "meta": {"total": 0, "limit": 50, "offset": 0}}


def test_list_calls_returns_seeded_rows_newest_first():
    db.upsert_call(
        "old", outcome="not_now", tier="COLD", score=5,
        started_at="2026-05-20T10:00:00+00:00",
    )
    db.upsert_call(
        "new", outcome="meeting_booked", tier="HOT", score=80,
        started_at="2026-05-22T10:00:00+00:00",
    )
    body = client.get("/api/calls").json()
    assert body["meta"]["total"] == 2
    assert [r["conversation_id"] for r in body["data"]] == ["new", "old"]


def test_list_calls_filters_by_outcome():
    db.upsert_call("a", outcome="meeting_booked", tier="HOT")
    db.upsert_call("b", outcome="not_now", tier="COLD")
    body = client.get("/api/calls?outcome=meeting_booked").json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["conversation_id"] == "a"


# --- /api/calls/{id} ----------------------------------------------------
def test_get_call_404_when_missing():
    assert client.get("/api/calls/nope").status_code == 404


def test_get_call_returns_row():
    db.upsert_call("c3", outcome="not_now", contact="Dr Lee")
    body = client.get("/api/calls/c3").json()
    assert body["data"]["conversation_id"] == "c3"
    assert body["data"]["contact"] == "Dr Lee"


# --- /api/leads ---------------------------------------------------------
def test_list_leads_groups_by_tier():
    db.upsert_call("h1", tier="HOT")
    db.upsert_call("w1", tier="WARM")
    db.upsert_call("d1", tier="DEAD")
    body = client.get("/api/leads").json()
    assert {t: len(rows) for t, rows in body["data"].items()} == {
        "HOT": 1, "WARM": 1, "COLD": 0, "DEAD": 1,
    }
    assert body["meta"] == {"HOT": 1, "WARM": 1, "COLD": 0, "DEAD": 1}


# --- /api/action-queue --------------------------------------------------
def test_action_queue_only_hot_warm_with_email_and_no_booking():
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).isoformat()

    # Eligible: HOT + email + no booking
    db.upsert_call("aq1", tier="HOT", email="a@b.uk", score=80)
    # Not eligible: HOT but no email captured
    db.upsert_call("aq2", tier="HOT", email="", score=70)
    # Not eligible: HOT + email but booking exists
    db.upsert_call("aq3", tier="HOT", email="c@d.uk", score=75)
    db.upsert_booking(
        uid="bk", conversation_id="aq3", start=future, attendee_email="c@d.uk",
    )
    # Not eligible: COLD tier
    db.upsert_call("aq4", tier="COLD", email="e@f.uk", score=10)

    body = client.get("/api/action-queue").json()
    assert [r["conversation_id"] for r in body["data"]] == ["aq1"]
    assert body["meta"] == {"total": 1}


# --- /api/bookings/upcoming --------------------------------------------
def test_bookings_upcoming_returns_envelope():
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).isoformat()
    db.upsert_booking(uid="b1", start=future, attendee_email="x@y.uk")
    body = client.get("/api/bookings/upcoming").json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["uid"] == "b1"


# --- /api/metrics -------------------------------------------------------
def test_metrics_endpoint_returns_today_envelope():
    body = client.get("/api/metrics?range=today").json()
    assert body["data"]["range"] == "today"
    assert body["data"]["calls"] == 0


# --- Bearer-token gate --------------------------------------------------
def test_auth_disabled_when_token_empty():
    # The autouse fixture cleared DASHBOARD_TOKEN.
    assert client.get("/api/calls").status_code == 200


def test_auth_required_when_token_is_set(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret-xyz")
    get_settings.cache_clear()

    assert client.get("/api/calls").status_code == 401
    assert client.get(
        "/api/calls", headers={"Authorization": "Bearer wrong"}
    ).status_code == 401
    assert client.get(
        "/api/calls", headers={"Authorization": "Bearer secret-xyz"}
    ).status_code == 200
