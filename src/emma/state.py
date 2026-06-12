"""Tiny JSON-file store for IDs produced at setup time.

Keeps the ElevenLabs agent id, phone-number id and tool ids so the CLI
commands chain together without hand-editing .env mid-flow.
"""

import json
from pathlib import Path
from typing import Any

_STATE_PATH = Path(".emma_state.json")


def load_state() -> dict[str, Any]:
    if not _STATE_PATH.exists():
        return {}
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(**values: Any) -> dict[str, Any]:
    """Merge non-None values into the state file and return the result."""
    state = load_state()
    state.update({k: v for k, v in values.items() if v is not None})
    _STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def get_value(key: str, default: Any = None) -> Any:
    return load_state().get(key, default)
