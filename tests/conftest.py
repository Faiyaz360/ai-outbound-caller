"""Shared test fixtures."""

import pytest

from emma.config import Settings


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Run every test in a temp dir so call_log.jsonl never leaks."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def settings() -> Settings:
    """A clean Settings object that ignores any real .env / env vars."""
    return Settings(
        _env_file=None,
        elevenlabs_api_key="test-el-key",
        elevenlabs_webhook_secret="test-secret",
        server_url="https://example.test",
        timezone="Europe/London",
    )
