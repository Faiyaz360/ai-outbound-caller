"""Tests for the FastAPI webhook server (ElevenLabs integration)."""

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from emma.config import get_settings
from emma.server import app, verify_signature

SECRET = "test-secret"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _server_secret(monkeypatch):
    """Make get_settings() inside the server return a known webhook secret."""
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _sign(body: bytes, secret: str = SECRET, timestamp: int | None = None) -> str:
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(
        secret.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return f"t={ts},v0={digest}"


def test_health_endpoint():
    assert client.get("/health").json() == {"status": "ok"}


# --- HMAC signature verification ----------------------------------------
def test_verify_signature_accepts_a_valid_signature():
    body = b'{"type":"post_call_transcription"}'
    assert verify_signature(body, _sign(body), SECRET) is True


def test_verify_signature_rejects_a_tampered_body():
    body = b'{"type":"post_call_transcription"}'
    signature = _sign(body)
    assert verify_signature(b'{"type":"tampered"}', signature, SECRET) is False


def test_verify_signature_rejects_a_wrong_secret():
    body = b'{"x":1}'
    assert verify_signature(body, _sign(body, secret="other-secret"), SECRET) is False


def test_verify_signature_rejects_a_malformed_header():
    assert verify_signature(b"{}", "garbage-no-equals", SECRET) is False
    assert verify_signature(b"{}", "", SECRET) is False


def test_verify_signature_rejects_a_stale_timestamp():
    body = b'{"x":1}'
    old = int(time.time()) - 9999  # well past the 30-minute tolerance
    assert verify_signature(body, _sign(body, timestamp=old), SECRET) is False


# --- Tool endpoints ------------------------------------------------------
def test_tool_endpoint_runs_the_tool_with_a_valid_secret():
    response = client.post(
        "/tools/log-call-outcome",
        json={"outcome": "not_now", "summary": "Prospect declined for now."},
        headers={"x-emma-tool-secret": SECRET},
    )
    assert response.status_code == 200
    assert "recorded" in response.json()["result"].lower()


def test_tool_endpoint_rejects_a_missing_secret():
    response = client.post(
        "/tools/log-call-outcome",
        json={"outcome": "not_now", "summary": "x"},
    )
    assert response.status_code == 401


# --- Post-call webhook ---------------------------------------------------
def test_post_call_webhook_accepts_a_signed_report():
    body = json.dumps(
        {
            "type": "post_call_transcription",
            "data": {
                "conversation_id": "conv_1",
                "status": "done",
                "analysis": {"transcript_summary": "Booked a discovery call."},
            },
        }
    ).encode()
    response = client.post(
        "/webhook/post-call",
        content=body,
        headers={"elevenlabs-signature": _sign(body)},
    )
    assert response.status_code == 200
    assert response.json() == {"received": True}
    logged = Path("call_log.jsonl").read_text(encoding="utf-8")
    assert "post_call_report" in logged


def test_post_call_webhook_rejects_an_invalid_signature():
    body = b'{"type":"post_call_transcription"}'
    response = client.post(
        "/webhook/post-call",
        content=body,
        headers={"elevenlabs-signature": _sign(body, secret="wrong-secret")},
    )
    assert response.status_code == 401


def test_post_call_webhook_persists_canonical_row_with_score():
    from emma import db

    body = json.dumps(
        {
            "type": "post_call_transcription",
            "data": {
                "conversation_id": "conv-pc-1",
                "status": "done",
                "metadata": {
                    "start_time_unix_secs": 1716200000,
                    "call_duration_secs": 180,
                },
                "transcript": [
                    {"role": "agent", "message": "Hi"},
                    {"role": "user", "message": "Yes the practice manager will join"},
                ],
                "analysis": {"transcript_summary": "Booked with practice manager."},
            },
        }
    ).encode()
    response = client.post(
        "/webhook/post-call",
        content=body,
        headers={"elevenlabs-signature": _sign(body)},
    )
    assert response.status_code == 200

    row = db.get_call("conv-pc-1")
    assert row is not None
    assert row["duration_s"] == 180
    assert "practice manager" in (row["transcript"] or "").lower()
    assert row["summary"] == "Booked with practice manager."
    # No outcome (0) + duration 180>60 (+10) + decision-maker keyword (+15) -> 25 / COLD
    assert row["score"] == 25
    assert row["tier"] == "COLD"


def test_post_call_webhook_merges_with_existing_tool_data():
    """Tool call wrote outcome+email earlier; post-call adds transcript and rescores."""
    from emma import db

    db.upsert_call(
        "conv-merge",
        outcome="meeting_booked",
        email="x@y.uk",
        contact="Dr Patel",
    )
    body = json.dumps(
        {
            "type": "post_call_transcription",
            "data": {
                "conversation_id": "conv-merge",
                "metadata": {"call_duration_secs": 240},
                "transcript": [{"role": "user", "message": "yes book it"}],
                "analysis": {"transcript_summary": "Booked."},
            },
        }
    ).encode()
    response = client.post(
        "/webhook/post-call",
        content=body,
        headers={"elevenlabs-signature": _sign(body)},
    )
    assert response.status_code == 200

    row = db.get_call("conv-merge")
    # Existing fields preserved.
    assert row["outcome"] == "meeting_booked"
    assert row["email"] == "x@y.uk"
    assert row["contact"] == "Dr Patel"
    # New fields applied.
    assert row["duration_s"] == 240
    assert row["summary"] == "Booked."
    # 50 (outcome) + 20 (email) + 10 (duration>60) = 80 -> HOT
    assert row["score"] == 80
    assert row["tier"] == "HOT"
