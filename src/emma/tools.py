"""Agent tools: the ElevenLabs webhook-tool schemas Emma can call, plus
the server-side handlers that run when she calls them.

If Cal.com is not configured the availability/booking tools degrade
gracefully to provisional slots so the demo still works end to end.
"""

import datetime as dt
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from emma import db
from emma.calcom import CalComClient, CalComError
from emma.config import Settings
from emma.events import hub
from emma.scoring import score_call

_CALL_LOG = Path("call_log.jsonl")

# Tool name -> URL slug for the webhook endpoint that serves it.
TOOL_SLUGS: dict[str, str] = {
    "check_availability": "check-availability",
    "book_meeting": "book-meeting",
    "log_call_outcome": "log-call-outcome",
}


# --- ElevenLabs webhook tool configs --------------------------------------
def elevenlabs_tool_configs(settings: Settings) -> list[dict[str, Any]]:
    """Tool configs in the shape POSTed to /v1/convai/tools.

    Each tool is a webhook pointing at this project's FastAPI server.
    """
    secret = settings.elevenlabs_webhook_secret
    headers = {"x-emma-tool-secret": secret} if secret else {}

    def webhook(name: str, description: str, body_schema: dict[str, Any]) -> dict:
        return {
            "type": "webhook",
            "name": name,
            "description": description,
            "api_schema": {
                "url": settings.tool_url(TOOL_SLUGS[name]),
                "method": "POST",
                "request_headers": headers,
                "request_body_schema": body_schema,
            },
        }

    return [
        webhook(
            "check_availability",
            (
                "Look up real open meeting slots before offering times to "
                "the prospect. Call this when ready to propose a meeting, "
                "then quote the slots it returns."
            ),
            {
                "type": "object",
                "description": "Optional search window for meeting slots.",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "How many days forward to search. Default 7.",
                    }
                },
                "required": [],
            },
        ),
        webhook(
            "book_meeting",
            (
                "Book the discovery call / demo into the calendar. Call this "
                "the moment the prospect agrees to a meeting. Use a start_iso "
                "value returned by check_availability."
            ),
            {
                "type": "object",
                "description": "Details needed to book the meeting.",
                "properties": {
                    "start_iso": {
                        "type": "string",
                        "description": "Meeting start, ISO-8601, from check_availability.",
                    },
                    "attendee_name": {
                        "type": "string",
                        "description": "Full name of the person being booked.",
                    },
                    "attendee_email": {
                        "type": "string",
                        "description": "Contact email for the calendar invite.",
                    },
                    "practice_name": {
                        "type": "string",
                        "description": "Name of the GP practice / surgery.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "One line of context (their pain points).",
                    },
                },
                "required": ["start_iso", "attendee_name", "attendee_email"],
            },
        ),
        webhook(
            "log_call_outcome",
            (
                "Record the result of this call, including the prospect's "
                "contact email if you captured one. Call once near the end "
                "of every call, whatever the outcome."
            ),
            {
                "type": "object",
                "description": "The outcome of the call and the lead's details.",
                "properties": {
                    "outcome": {
                        "type": "string",
                        "description": (
                            "One of: meeting_booked, pilot_agreed, "
                            "follow_up_scheduled, not_now, do_not_call."
                        ),
                    },
                    "summary": {
                        "type": "string",
                        "description": "One or two sentences on what happened.",
                    },
                    "contact_name": {
                        "type": "string",
                        "description": "Who you spoke to, if known.",
                    },
                    "email": {
                        "type": "string",
                        "description": (
                            "The prospect's contact email, if captured - "
                            "always try, so the team can send a follow-up "
                            "demo video."
                        ),
                    },
                    "practice_name": {
                        "type": "string",
                        "description": "Name of the GP practice / surgery, if known.",
                    },
                },
                "required": ["outcome", "summary"],
            },
        ),
    ]


# --- Dispatch ------------------------------------------------------------
async def handle_tool_call(
    name: str,
    arguments: dict[str, Any],
    settings: Settings,
    *,
    conversation_id: str | None = None,
    calcom: CalComClient | None = None,
) -> str:
    """Run one tool call and return a plain-text result for the model.

    When `conversation_id` is supplied (ElevenLabs sends it as a header or
    in the body of webhook-tool requests), the relevant SQLite row is
    upserted so the dashboard sees the result the moment Emma calls the
    tool - not only after the post-call webhook lands.
    """
    if name == "check_availability":
        return await _check_availability(arguments, settings, calcom)
    if name == "book_meeting":
        return await _book_meeting(arguments, settings, calcom, conversation_id)
    if name == "log_call_outcome":
        return _log_call_outcome(arguments, conversation_id)
    return f"Unknown tool '{name}'. No such tool is available."


# --- Individual handlers -------------------------------------------------
async def _check_availability(
    args: dict[str, Any], settings: Settings, calcom: CalComClient | None
) -> str:
    if not _calcom_configured(settings):
        return _format_slots(_fallback_slots(settings), settings)

    days_ahead = int(args.get("days_ahead") or 7)
    client = calcom or CalComClient(settings)
    try:
        slots = await client.get_available_slots(days_ahead=days_ahead)
    except CalComError:
        return _format_slots(
            _fallback_slots(settings), settings, note="(provisional times)"
        )
    if not slots:
        slots = _fallback_slots(settings)
    return _format_slots(slots, settings)


async def _book_meeting(
    args: dict[str, Any],
    settings: Settings,
    calcom: CalComClient | None,
    conversation_id: str | None = None,
) -> str:
    start_iso = str(args.get("start_iso") or "").strip()
    name = str(args.get("attendee_name") or "").strip()
    email = str(args.get("attendee_email") or "").strip()
    practice = str(args.get("practice_name") or "").strip()
    notes = str(args.get("notes") or "").strip()

    if not start_iso or not name or not email:
        return (
            "I still need a meeting time, the contact's name and an email "
            "before I can book. Ask the prospect for whatever is missing, "
            "then call book_meeting again."
        )

    spoken = _speak_time(start_iso, settings.timezone)

    booked_uid: str
    confirmation: str

    if not _calcom_configured(settings):
        append_call_log(
            {
                "event": "booking_provisional",
                "start": start_iso,
                "name": name,
                "email": email,
                "practice": practice,
                "notes": notes,
            }
        )
        booked_uid = f"provisional-{start_iso}-{email}"
        confirmation = (
            f"Meeting provisionally booked for {spoken}. A calendar invite "
            f"will go to {email}. Confirm this back to the prospect clearly."
        )
    else:
        client = calcom or CalComClient(settings)
        try:
            booking = await client.create_booking(
                start_iso=start_iso,
                attendee_name=name,
                attendee_email=email,
                practice_name=practice,
                notes=notes,
            )
        except CalComError as exc:
            append_call_log(
                {"event": "booking_failed", "error": str(exc), "start": start_iso}
            )
            return (
                "That exact slot would not confirm. Apologise lightly, offer the "
                "prospect another time, then call book_meeting again."
            )
        booked_uid = str(booking.get("uid") or f"calcom-{start_iso}-{email}")
        append_call_log(
            {
                "event": "booking_confirmed",
                "start": start_iso,
                "name": name,
                "email": email,
                "practice": practice,
                "uid": booked_uid,
            }
        )
        confirmation = (
            f"Booked. The meeting is confirmed for {spoken} and an invite is on "
            f"its way to {email}. Confirm the date and time back to the prospect "
            f"clearly, then wrap up warmly."
        )

    # Persist to SQLite so the dashboard sees the booking immediately.
    db.upsert_booking(
        uid=booked_uid,
        conversation_id=conversation_id or "",
        start=start_iso,
        attendee_name=name,
        attendee_email=email,
        practice=practice,
    )
    hub.publish(
        "booking_created",
        uid=booked_uid,
        conversation_id=conversation_id or "",
        start=start_iso,
    )
    if conversation_id:
        db.upsert_call(
            conversation_id,
            outcome="meeting_booked",
            contact=name,
            email=email,
            practice=practice,
        )
        _rescore(conversation_id)
        hub.publish(
            "call_updated",
            conversation_id=conversation_id,
            outcome="meeting_booked",
        )

    return confirmation


def _log_call_outcome(
    args: dict[str, Any], conversation_id: str | None = None
) -> str:
    outcome = str(args.get("outcome") or "unknown")
    contact = str(args.get("contact_name") or "")
    email = str(args.get("email") or "")
    practice = str(args.get("practice_name") or "")
    summary = str(args.get("summary") or "")

    append_call_log(
        {
            "event": "call_outcome",
            "outcome": outcome,
            "contact": contact,
            "email": email,
            "practice": practice,
            "summary": summary,
        }
    )

    if conversation_id:
        db.upsert_call(
            conversation_id,
            outcome=outcome,
            contact=contact,
            email=email,
            practice=practice,
            summary=summary,
        )
        _rescore(conversation_id)
        hub.publish(
            "call_updated",
            conversation_id=conversation_id,
            outcome=outcome,
        )

    return f"Outcome '{outcome}' recorded. You may close the call."


def _rescore(conversation_id: str) -> None:
    """Recompute score for one call after its DB row has been updated."""
    row = db.get_call(conversation_id) or {}
    transcript = str(row.get("transcript") or "") or None
    s = score_call(row, transcript=transcript)
    db.upsert_call(
        conversation_id,
        score=s.score,
        tier=s.tier,
        score_reasons=s.reasons,
    )


# --- Helpers -------------------------------------------------------------
def _calcom_configured(settings: Settings) -> bool:
    return bool(settings.calcom_api_key and settings.calcom_event_type_id)


def _fallback_slots(settings: Settings, count: int = 6) -> list[str]:
    """Synthesise weekday 10:00 / 14:00 slots when Cal.com is not wired."""
    tz = ZoneInfo(settings.timezone)
    day = dt.datetime.now(tz) + dt.timedelta(days=1)
    out: list[str] = []
    while len(out) < count:
        if day.weekday() < 5:  # Monday-Friday
            for hour in (10, 14):
                slot = day.replace(hour=hour, minute=0, second=0, microsecond=0)
                out.append(slot.astimezone(dt.timezone.utc).isoformat())
        day += dt.timedelta(days=1)
    return out[:count]


def _format_slots(slots: list[str], settings: Settings, note: str = "") -> str:
    if not slots:
        return "No open slots in that window. Try a wider days_ahead value."
    lines = [
        f"- {_speak_time(s, settings.timezone)}  (start_iso: {s})"
        for s in slots
    ]
    header = "Open meeting slots" + (f" {note}" if note else "") + ":"
    return header + "\n" + "\n".join(lines)


def _speak_time(iso: str, tz_name: str) -> str:
    """Format an ISO datetime into something natural to say aloud."""
    try:
        moment = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if moment.tzinfo is not None:
        try:
            moment = moment.astimezone(ZoneInfo(tz_name))
        except Exception:  # noqa: BLE001 - bad tz name should not crash a call
            pass
    return moment.strftime("%A %d %B at %I:%M %p").replace(" 0", " ")


def append_call_log(record: dict[str, Any]) -> None:
    """Append one timestamped record to call_log.jsonl (shared by server)."""
    record = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), **record}
    with _CALL_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
