"""Tests for Emma's ElevenLabs agent prompt assembly."""

from emma.prompt import build_first_message, build_system_prompt


def test_system_prompt_uses_elevenlabs_six_block_format(settings):
    prompt = build_system_prompt(settings)
    for block in (
        "# Personality",
        "# Environment",
        "# Tone",
        "# Goal",
        "# Guardrails",
        "# Tools",
    ):
        assert block in prompt


def test_system_prompt_includes_verified_company_facts(settings):
    prompt = build_system_prompt(settings)
    # Proof points Emma is allowed to quote.
    assert "80%" in prompt
    assert "DTAC" in prompt
    assert "81%" in prompt


def test_system_prompt_carries_closer_methodology(settings):
    prompt = build_system_prompt(settings)
    assert "LAARC" in prompt
    assert "Validate-Isolate-Reframe" in prompt
    assert "ASK LADDER" in prompt
    assert "OPENING, not an ending" in prompt


def test_system_prompt_resists_early_brush_offs(settings):
    prompt = build_system_prompt(settings)
    assert "re-engagement attempt" in prompt
    assert "NOT a hard stop" in prompt


def test_system_prompt_drives_toward_booking(settings):
    prompt = build_system_prompt(settings)
    assert "book_meeting" in prompt
    assert "PRIMARY - book a meeting" in prompt


def test_system_prompt_handles_voicemail(settings):
    prompt = build_system_prompt(settings)
    assert "## Voicemail" in prompt
    assert "20 seconds" in prompt


def test_system_prompt_requires_honest_ai_disclosure(settings):
    prompt = build_system_prompt(settings)
    assert "Never claim to be human" in prompt
    assert "asked whether you are an AI" in prompt


def test_first_message_is_a_no_oriented_opener(settings):
    message = build_first_message(settings)
    assert settings.agent_name in message
    assert settings.company_name in message
    # A "no"-oriented opener invites a safe, guard-lowering "no".
    assert "bad moment" in message.lower()
