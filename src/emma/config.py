"""Runtime configuration loaded from environment / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All tunable settings for the Emma outbound agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- ElevenLabs Agents (the agent is built in the dashboard) ---
    # Voice + LLM live on the dashboard agent, not here.
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_phone_number_id: str = ""
    elevenlabs_webhook_secret: str = ""
    # Optional bearer token for the dashboard /api/* endpoints. Empty = open.
    dashboard_token: str = ""

    # --- Twilio (raw UK number, imported into ElevenLabs) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # --- Cal.com ---
    calcom_api_key: str = ""
    calcom_event_type_id: int = 0

    # --- Webhook server ---
    server_url: str = ""

    # --- Demo ---
    target_test_number: str = ""

    # --- Identity (rarely changed) ---
    company_name: str = "QuantumLoopAI"
    agent_name: str = "Emma"
    timezone: str = "Europe/London"

    def tool_url(self, slug: str) -> str:
        """Public URL ElevenLabs calls for one webhook tool."""
        return f"{self.server_url.rstrip('/')}/tools/{slug}"

    def require(self, *fields: str) -> None:
        """Raise a clear error if any required setting is empty."""
        missing = [f for f in fields if not getattr(self, f, None)]
        if missing:
            raise RuntimeError(
                "Missing required settings in .env: " + ", ".join(missing)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
