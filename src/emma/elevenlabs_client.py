"""Async client for the ElevenLabs Agents (Conversational AI) REST API.

The agent itself is built and edited in the ElevenLabs dashboard. This
client only drives the phone side: importing the Twilio number and placing
an outbound call. All calls go over httpx - no extra SDK dependency.
"""

from typing import Any

import httpx

from emma.config import Settings

_BASE_URL = "https://api.elevenlabs.io"
_TIMEOUT = 30.0


class ElevenLabsError(RuntimeError):
    """Raised when ElevenLabs returns an error or is unreachable."""


class ElevenLabsClient:
    def __init__(self, settings: Settings, *, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "xi-api-key": self._settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        }

    async def _send(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = _BASE_URL + path
        try:
            if self._client is not None:
                resp = await self._client.request(
                    method, url, headers=self._headers, json=json, params=params
                )
            else:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.request(
                        method, url, headers=self._headers, json=json, params=params
                    )
        except httpx.HTTPError as exc:
            raise ElevenLabsError(f"ElevenLabs request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise ElevenLabsError(
                f"ElevenLabs {method} {path} -> {resp.status_code}: {resp.text}"
            )
        return resp.json() if resp.content else {}

    async def import_twilio_number(self) -> dict[str, Any]:
        """Register the configured Twilio number with ElevenLabs."""
        body = {
            "provider": "twilio",
            "phone_number": self._settings.twilio_phone_number,
            "label": f"{self._settings.agent_name} Outbound",
            "sid": self._settings.twilio_account_sid,
            "token": self._settings.twilio_auth_token,
        }
        return await self._send("POST", "/v1/convai/phone-numbers", json=body)

    async def outbound_call(
        self, *, agent_id: str, phone_number_id: str, to_number: str
    ) -> dict[str, Any]:
        """Place an outbound call via ElevenLabs' native Twilio integration."""
        body = {
            "agent_id": agent_id,
            "agent_phone_number_id": phone_number_id,
            "to_number": to_number,
        }
        return await self._send(
            "POST", "/v1/convai/twilio/outbound-call", json=body
        )
