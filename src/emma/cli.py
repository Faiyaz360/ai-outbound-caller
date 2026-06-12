"""Command-line tools for the Emma outbound sales agent.

Emma's agent is built and edited in the ElevenLabs dashboard. These
commands drive the phone side of it:

  emma import-number    Import the Twilio number into ElevenLabs
  emma call [number]    Place an outbound call (defaults to TARGET_TEST_NUMBER)
  emma serve            Run the Cal.com tool webhook server on :8000
  emma status           Show configuration and stored ids
"""

import argparse
import asyncio
import sys

from emma.config import Settings, get_settings
from emma.elevenlabs_client import ElevenLabsClient, ElevenLabsError
from emma.state import get_value, save_state


async def _cmd_import_number(settings: Settings) -> None:
    settings.require(
        "elevenlabs_api_key",
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_phone_number",
    )
    result = await ElevenLabsClient(settings).import_twilio_number()
    number_id = result.get("phone_number_id") or result.get("id", "")
    save_state(phone_number_id=number_id)
    print(f"Imported {settings.twilio_phone_number}")
    print(f"  phone_number_id: {number_id}  (saved to .emma_state.json)")


async def _cmd_call(settings: Settings, number: str | None) -> None:
    settings.require("elevenlabs_api_key")
    agent_id = settings.elevenlabs_agent_id or get_value("agent_id")
    phone_number_id = (
        get_value("phone_number_id") or settings.elevenlabs_phone_number_id
    )
    target = number or settings.target_test_number

    if not agent_id:
        raise SystemExit(
            "No agent id. Set ELEVENLABS_AGENT_ID in .env - copy it from "
            "the ElevenLabs dashboard."
        )
    if not phone_number_id:
        raise SystemExit("No phone number. Run `emma import-number` first.")
    if not target:
        raise SystemExit(
            "No target number. Pass one or set TARGET_TEST_NUMBER in .env."
        )

    result = await ElevenLabsClient(settings).outbound_call(
        agent_id=agent_id,
        phone_number_id=phone_number_id,
        to_number=target,
    )
    print(f"Calling {target} ...  {result}")
    print("Answer it and keep saying no. Watch call_log.jsonl for tool calls.")


def _cmd_serve(settings: Settings) -> None:
    import uvicorn

    if not settings.server_url:
        print("Warning: SERVER_URL is empty - set it so ElevenLabs can reach you.")
    print("Webhook server starting on http://0.0.0.0:8000")
    print("Expose it publicly (e.g. `ngrok http 8000`) and set SERVER_URL.")
    uvicorn.run("emma.server:app", host="0.0.0.0", port=8000, reload=False)


def _cmd_status(settings: Settings) -> None:
    def mark(value: object) -> str:
        return "set" if value else "MISSING"

    print("=== Emma configuration ===")
    print(f"  ElevenLabs API key : {mark(settings.elevenlabs_api_key)}")
    print(f"  ElevenLabs agent   : {settings.elevenlabs_agent_id or 'MISSING'}")
    print(f"  Webhook secret     : {mark(settings.elevenlabs_webhook_secret)}")
    print(f"  Twilio number      : {settings.twilio_phone_number or 'MISSING'}")
    print(f"  Cal.com API key    : {mark(settings.calcom_api_key)}")
    print(f"  Cal.com event id   : {settings.calcom_event_type_id or 'MISSING'}")
    print(f"  Server URL         : {settings.server_url or 'MISSING'}")
    print(f"  Test number        : {settings.target_test_number or 'MISSING'}")
    print("=== Stored state (.emma_state.json) ===")
    print(f"  phone_number_id    : {get_value('phone_number_id') or 'not imported'}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="emma", description="Emma - outbound AI sales agent"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("import-number", help="Import the Twilio number into ElevenLabs")
    call_parser = sub.add_parser("call", help="Place an outbound call")
    call_parser.add_argument(
        "number", nargs="?", help="Target number; defaults to TARGET_TEST_NUMBER"
    )
    sub.add_parser("serve", help="Run the webhook server")
    sub.add_parser("status", help="Show configuration and stored ids")
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        if args.command == "import-number":
            asyncio.run(_cmd_import_number(settings))
        elif args.command == "call":
            asyncio.run(_cmd_call(settings, args.number))
        elif args.command == "serve":
            _cmd_serve(settings)
        elif args.command == "status":
            _cmd_status(settings)
    except (ElevenLabsError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
