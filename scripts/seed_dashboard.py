"""Seed `emma.db` with a handful of demo calls + a booking so the
dashboard renders something useful without running a live phone session.

Usage (from project root, in the venv):

    python scripts/seed_dashboard.py

Idempotent - re-running just overwrites the same rows. Wipe the DB by
deleting `emma.db` first if you want a clean slate.
"""

import datetime as dt
import sys
from pathlib import Path

# Allow `python scripts/seed_dashboard.py` to import the local package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emma import db
from emma.scoring import score_call


def _seed_call(
    conversation_id: str,
    *,
    started_at: str,
    contact: str,
    email: str,
    practice: str,
    outcome: str,
    summary: str,
    duration_s: int,
    transcript: str = "",
) -> None:
    rec = {
        "outcome": outcome,
        "email": email,
        "summary": summary,
        "duration_s": duration_s,
    }
    s = score_call(rec, transcript=transcript or None)
    db.upsert_call(
        conversation_id,
        started_at=started_at,
        contact=contact,
        email=email,
        practice=practice,
        outcome=outcome,
        summary=summary,
        duration_s=duration_s,
        transcript=transcript,
        score=s.score,
        tier=s.tier,
        score_reasons=s.reasons,
    )


def main() -> None:
    db.init_db()
    now = dt.datetime.now(dt.timezone.utc)

    _seed_call(
        "demo-hot-booked",
        started_at=(now - dt.timedelta(hours=1)).isoformat(),
        contact="Dr Jane Patel",
        email="jane@riverside.nhs.uk",
        practice="Riverside Surgery",
        outcome="meeting_booked",
        summary="Spoke to the practice manager. Booked discovery call for Thursday.",
        duration_s=240,
        transcript=(
            "agent: Hi there - this is Emma calling from QuantumLoopAI. "
            "Is now a bad moment?\n"
            "user: Hi, what's this about?\n"
            "agent: I work with GP surgeries to end the 8am phone queue. "
            "How many reception staff handle your mornings?\n"
            "user: Three. The practice manager owns staffing.\n"
            "agent: Perfect - could I grab fifteen minutes with her on "
            "Thursday at two?\n"
            "user: That works."
        ),
    )

    _seed_call(
        "demo-warm-followup",
        started_at=(now - dt.timedelta(days=1)).isoformat(),
        contact="Sara Ops Manager",
        email="ops@northpark.nhs.uk",
        practice="North Park Health Centre",
        outcome="follow_up_scheduled",
        summary="Sending demo video. Calling back Friday when the partner is in.",
        duration_s=180,
    )

    _seed_call(
        "demo-cold-not-now",
        started_at=(now - dt.timedelta(hours=3)).isoformat(),
        contact="Dr Mark Lee",
        email="lee@hillview.nhs.uk",
        practice="Hillview Practice",
        outcome="not_now",
        summary="Mid-audit. Wants a demo video; revisit next month.",
        duration_s=90,
    )

    _seed_call(
        "demo-dead-dnc",
        started_at=(now - dt.timedelta(hours=6)).isoformat(),
        contact="Reception",
        email="",
        practice="Greenfield Surgery",
        outcome="do_not_call",
        summary="Asked to be removed. Marked do_not_call.",
        duration_s=20,
    )

    db.upsert_booking(
        uid="bk-demo-hot-booked",
        conversation_id="demo-hot-booked",
        start=(now + dt.timedelta(days=2)).isoformat(),
        attendee_name="Dr Jane Patel",
        attendee_email="jane@riverside.nhs.uk",
        practice="Riverside Surgery",
    )

    print("Seeded 4 calls + 1 booking into emma.db")
    print("Start the backend:  emma serve")
    print("Start the dashboard: cd dashboard && npm run dev")
    print("Then open http://localhost:3100")


if __name__ == "__main__":
    main()
