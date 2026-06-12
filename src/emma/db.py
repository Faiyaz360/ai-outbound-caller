"""SQLite store for the Emma dashboard.

One file (`emma.db`) in cwd. WAL mode. Keyed by ElevenLabs
conversation_id so the post-call webhook and the tool handlers can each
UPSERT the same row without race conditions on JSONL appends.

Scoring is persisted alongside each row (score-at-write); the dashboard
JSON API reads only and never recomputes.
"""

import datetime as dt
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

_DB_PATH = Path("emma.db")
_LOCK = threading.RLock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    conversation_id TEXT PRIMARY KEY,
    started_at      TEXT,
    duration_s      INTEGER DEFAULT 0,
    contact         TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    practice        TEXT DEFAULT '',
    outcome         TEXT DEFAULT '',
    summary         TEXT DEFAULT '',
    transcript      TEXT DEFAULT '',
    analysis        TEXT DEFAULT '{}',
    score           INTEGER DEFAULT 0,
    tier            TEXT DEFAULT 'DEAD',
    score_reasons   TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_calls_tier       ON calls(tier);
CREATE INDEX IF NOT EXISTS idx_calls_outcome    ON calls(outcome);

CREATE TABLE IF NOT EXISTS bookings (
    uid             TEXT PRIMARY KEY,
    conversation_id TEXT DEFAULT '',
    start           TEXT,
    attendee_name   TEXT DEFAULT '',
    attendee_email  TEXT DEFAULT '',
    practice        TEXT DEFAULT '',
    created_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables (idempotent). Safe to call on every startup."""
    with _LOCK, _connect() as conn:
        conn.executescript(_SCHEMA)


# --- Calls --------------------------------------------------------------
_CALL_COLUMNS = {
    "started_at", "duration_s", "contact", "email", "practice",
    "outcome", "summary", "transcript", "analysis",
    "score", "tier", "score_reasons",
}


def upsert_call(conversation_id: str, **fields: Any) -> None:
    """Insert or update one call row. Only sets columns present in fields.

    `analysis` and `score_reasons` may be passed as dict/list and will be
    serialised to JSON. Anything else outside _CALL_COLUMNS is ignored.
    """
    init_db()
    clean: dict[str, Any] = {}
    for k, v in fields.items():
        if k not in _CALL_COLUMNS or v is None:
            continue
        if k in ("analysis", "score_reasons") and not isinstance(v, str):
            clean[k] = json.dumps(v)
        else:
            clean[k] = v

    with _LOCK, _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM calls WHERE conversation_id = ?", (conversation_id,)
        ).fetchone() is not None

        if exists and clean:
            sets = ", ".join(f"{k} = ?" for k in clean)
            conn.execute(
                f"UPDATE calls SET {sets} WHERE conversation_id = ?",
                (*clean.values(), conversation_id),
            )
        elif not exists:
            clean.setdefault("started_at", _now())
            clean["conversation_id"] = conversation_id
            cols = ", ".join(clean)
            placeholders = ", ".join("?" * len(clean))
            conn.execute(
                f"INSERT INTO calls ({cols}) VALUES ({placeholders})",
                tuple(clean.values()),
            )


def get_call(conversation_id: str) -> dict[str, Any] | None:
    init_db()
    with _LOCK, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM calls WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        return _row_to_call(row) if row else None


def list_calls(
    *,
    limit: int = 50,
    offset: int = 0,
    outcome: str | None = None,
    tier: str | None = None,
    from_iso: str | None = None,
    to_iso: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return (rows newest-first, total matching count)."""
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if outcome:
        where.append("outcome = ?")
        params.append(outcome)
    if tier:
        where.append("tier = ?")
        params.append(tier)
    if from_iso:
        where.append("started_at >= ?")
        params.append(from_iso)
    if to_iso:
        where.append("started_at <= ?")
        params.append(to_iso)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    with _LOCK, _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM calls{where_sql}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM calls{where_sql} "
            "ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return [_row_to_call(r) for r in rows], int(total)


def _row_to_call(row: sqlite3.Row) -> dict[str, Any]:
    """Hydrate JSON fields back into structured values."""
    record = dict(row)
    for json_field in ("analysis", "score_reasons"):
        raw = record.get(json_field)
        if isinstance(raw, str) and raw:
            try:
                record[json_field] = json.loads(raw)
            except json.JSONDecodeError:
                pass
    return record


# --- Bookings -----------------------------------------------------------
def upsert_booking(
    *,
    uid: str,
    conversation_id: str = "",
    start: str = "",
    attendee_name: str = "",
    attendee_email: str = "",
    practice: str = "",
) -> None:
    init_db()
    with _LOCK, _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO bookings
                 (uid, conversation_id, start, attendee_name, attendee_email,
                  practice, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (uid, conversation_id, start, attendee_name, attendee_email,
             practice, _now()),
        )


def list_upcoming_bookings(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    now = _now()
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE start >= ? "
            "ORDER BY start ASC LIMIT ?",
            (now, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# --- Metrics ------------------------------------------------------------
def metrics(range_: str = "today") -> dict[str, Any]:
    """Aggregates over recent calls. range_ in {today, week, month}."""
    init_db()
    now = dt.datetime.now(dt.timezone.utc)
    if range_ == "week":
        since = (now - dt.timedelta(days=7)).isoformat()
    elif range_ == "month":
        since = (now - dt.timedelta(days=30)).isoformat()
    else:
        since = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

    with _LOCK, _connect() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*)                                              AS calls,
                 SUM(CASE WHEN email <> ''               THEN 1 ELSE 0 END) AS with_email,
                 SUM(CASE WHEN outcome = 'meeting_booked' THEN 1 ELSE 0 END) AS booked,
                 AVG(duration_s)                                       AS avg_duration
               FROM calls WHERE started_at >= ?""",
            (since,),
        ).fetchone()

    calls = int(row["calls"] or 0)
    with_email = int(row["with_email"] or 0)
    booked = int(row["booked"] or 0)
    return {
        "range": range_,
        "calls": calls,
        "contact_capture_pct": round(100 * with_email / calls, 1) if calls else 0.0,
        "booking_rate_pct": round(100 * booked / calls, 1) if calls else 0.0,
        "avg_duration_s": round(float(row["avg_duration"] or 0), 1),
    }


# --- Leads (grouped + action queue) -------------------------------------
def list_leads_by_tier() -> dict[str, list[dict[str, Any]]]:
    """All calls grouped into the 4 tier buckets, newest first per bucket."""
    init_db()
    buckets: dict[str, list[dict[str, Any]]] = {
        "HOT": [], "WARM": [], "COLD": [], "DEAD": [],
    }
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM calls ORDER BY started_at DESC"
        ).fetchall()
    for r in rows:
        rec = _row_to_call(r)
        bucket = buckets.get(str(rec.get("tier") or "DEAD"))
        if bucket is not None:
            bucket.append(rec)
    return buckets


def list_action_queue(limit: int = 50) -> list[dict[str, Any]]:
    """Hot or warm leads with a captured email and no booking on file yet."""
    init_db()
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM calls
                 WHERE tier IN ('HOT','WARM')
                   AND email <> ''
                   AND conversation_id NOT IN (
                         SELECT conversation_id FROM bookings
                          WHERE conversation_id <> ''
                       )
                 ORDER BY score DESC, started_at DESC
                 LIMIT ?""",
            (limit,),
        ).fetchall()
    return [_row_to_call(r) for r in rows]
