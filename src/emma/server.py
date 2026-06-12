"""FastAPI webhook server for the ElevenLabs-powered Emma agent.

ElevenLabs runs the call (brain, voice, telephony). This server only:
  - serves the 3 Cal.com tool endpoints ElevenLabs calls mid-conversation
  - receives the post-call webhook (transcript + summary)

Tool endpoints are guarded by a shared-secret header. The post-call
webhook is verified with ElevenLabs' HMAC signature.
"""

import datetime as dt
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import FastAPI, Request, Response

from emma import db
from emma.config import get_settings
from emma.dashboard_api import router as dashboard_router
from emma.events import hub
from emma.scoring import score_call
from emma.tools import append_call_log, handle_tool_call

app = FastAPI(title="Emma Outbound Webhook (ElevenLabs)")
app.include_router(dashboard_router)

_TOOL_SECRET_HEADER = "x-emma-tool-secret"
_SIGNATURE_HEADER = "elevenlabs-signature"
_SIGNATURE_TOLERANCE_SECONDS = 30 * 60


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tools/check-availability")
async def tool_check_availability(request: Request) -> Any:
    return await _run_tool("check_availability", request)


@app.post("/tools/book-meeting")
async def tool_book_meeting(request: Request) -> Any:
    return await _run_tool("book_meeting", request)


@app.post("/tools/log-call-outcome")
async def tool_log_call_outcome(request: Request) -> Any:
    return await _run_tool("log_call_outcome", request)


@app.post("/webhook/post-call")
async def post_call_webhook(request: Request) -> Any:
    settings = get_settings()
    raw_body = await request.body()
    signature = request.headers.get(_SIGNATURE_HEADER, "")

    if not verify_signature(raw_body, signature, settings.elevenlabs_webhook_secret):
        return Response(status_code=401, content="invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        payload = {}
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    analysis = data.get("analysis") or {}
    conversation_id = str(data.get("conversation_id") or "")
    summary = str(analysis.get("transcript_summary") or "")

    # Durable audit log (kept for parity with the existing JSONL trail).
    append_call_log(
        {
            "event": "post_call_report",
            "report_type": payload.get("type") if isinstance(payload, dict) else None,
            "conversation_id": conversation_id,
            "status": data.get("status"),
            "summary": summary,
        }
    )

    if conversation_id:
        _persist_post_call(conversation_id, data, analysis, summary)
        hub.publish(
            "call_updated",
            conversation_id=conversation_id,
            source="post_call",
        )

    return {"received": True}


def _persist_post_call(
    conversation_id: str,
    data: dict[str, Any],
    analysis: dict[str, Any],
    summary: str,
) -> None:
    """Build the canonical call row + score from the post-call payload."""
    metadata = data.get("metadata") or {}
    start_unix = metadata.get("start_time_unix_secs")
    started_at = (
        dt.datetime.fromtimestamp(start_unix, dt.timezone.utc).isoformat()
        if isinstance(start_unix, (int, float)) and start_unix > 0
        else None
    )
    duration_s = int(metadata.get("call_duration_secs") or 0)

    transcript_turns = data.get("transcript") or []
    transcript_text = "\n".join(
        f"{turn.get('role', '?')}: {turn.get('message', '')}"
        for turn in transcript_turns
        if isinstance(turn, dict) and turn.get("message")
    )

    # Merge with any tool-time data so the score covers the full call.
    existing = db.get_call(conversation_id) or {}
    merged = {
        "outcome": existing.get("outcome", ""),
        "email": existing.get("email", ""),
        "summary": summary or existing.get("summary", ""),
        "duration_s": duration_s or existing.get("duration_s", 0),
    }
    s = score_call(merged, transcript=transcript_text or None)

    db.upsert_call(
        conversation_id,
        started_at=started_at,
        duration_s=duration_s,
        summary=summary,
        transcript=transcript_text,
        analysis=analysis,
        score=s.score,
        tier=s.tier,
        score_reasons=s.reasons,
    )


async def _run_tool(tool_name: str, request: Request) -> Any:
    """Validate the shared secret, run the tool, return its result."""
    settings = get_settings()
    secret = settings.elevenlabs_webhook_secret
    if secret and request.headers.get(_TOOL_SECRET_HEADER) != secret:
        return Response(status_code=401, content="bad tool secret")

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        payload = {}
    args = payload if isinstance(payload, dict) else {}

    # ElevenLabs may send the conversation id as a header or in the body.
    # Pop it from args so it never reaches the tool as a real parameter.
    conversation_id = (
        request.headers.get("elevenlabs-conversation-id")
        or request.headers.get("x-elevenlabs-conversation-id")
        or args.pop("conversation_id", None)
        or ""
    )

    try:
        result = await handle_tool_call(
            tool_name,
            args,
            settings,
            conversation_id=conversation_id or None,
        )
    except Exception as exc:  # noqa: BLE001 - never 500 a live call
        append_call_log(
            {"event": "tool_error", "tool": tool_name, "error": str(exc)}
        )
        result = f"The {tool_name} tool hit a problem. Carry on and try again."
    return {"result": result}


def verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify an ElevenLabs HMAC webhook signature (`t=<ts>,v0=<hex>`).

    Returns True when no secret is configured (verification disabled).
    """
    if not secret:
        return True
    if not signature_header:
        return False

    parts = dict(
        piece.split("=", 1)
        for piece in signature_header.split(",")
        if "=" in piece
    )
    timestamp = parts.get("t", "")
    provided = parts.get("v0", "")
    if not timestamp or not provided:
        return False

    try:
        age = abs(time.time() - int(timestamp))
    except ValueError:
        return False
    if age > _SIGNATURE_TOLERANCE_SECONDS:
        return False

    signed = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(
        secret.encode("utf-8"), signed, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, provided)
