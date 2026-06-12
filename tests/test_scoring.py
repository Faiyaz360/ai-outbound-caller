"""Tests for the rules-based lead scorer."""

from emma.scoring import score_call, tier_for_score


def test_tier_boundaries():
    assert tier_for_score(0) == "DEAD"
    assert tier_for_score(-10) == "DEAD"
    assert tier_for_score(1) == "COLD"
    assert tier_for_score(29) == "COLD"
    assert tier_for_score(30) == "WARM"
    assert tier_for_score(59) == "WARM"
    assert tier_for_score(60) == "HOT"
    assert tier_for_score(999) == "HOT"


def test_meeting_booked_with_email_is_hot():
    s = score_call(
        {"outcome": "meeting_booked", "email": "x@y.uk", "duration_s": 120}
    )
    # 50 (outcome) + 20 (email) + 10 (duration) = 80
    assert s.score == 80
    assert s.tier == "HOT"
    assert any("meeting_booked" in r for r in s.reasons)
    assert any("email" in r for r in s.reasons)


def test_do_not_call_is_dead_even_with_email():
    s = score_call({"outcome": "do_not_call", "email": "x@y.uk"})
    # -50 + 20 = -30 -> DEAD
    assert s.tier == "DEAD"
    assert s.score == -30


def test_not_now_with_email_is_cold():
    s = score_call({"outcome": "not_now", "email": "x@y.uk"})
    # 5 + 20 = 25 -> COLD
    assert s.score == 25
    assert s.tier == "COLD"


def test_decision_maker_keyword_bumps_score():
    base = score_call({"outcome": "not_now"})
    with_dm = score_call(
        {"outcome": "not_now", "summary": "Spoke to the Practice Manager."}
    )
    assert with_dm.score == base.score + 15


def test_transcript_used_when_summary_missing_keyword():
    s = score_call(
        {"outcome": "follow_up_scheduled"},
        transcript="They said the partner would call back tomorrow.",
    )
    # 25 (outcome) + 15 (decision-maker via transcript) = 40 -> WARM
    assert s.score == 40
    assert s.tier == "WARM"


def test_empty_record_is_dead():
    s = score_call({})
    assert s.score == 0
    assert s.tier == "DEAD"
    assert s.reasons == []


def test_unknown_outcome_does_not_crash():
    s = score_call({"outcome": "exploded"})
    assert s.score == 0
    assert s.tier == "DEAD"
