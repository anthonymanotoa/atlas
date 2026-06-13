"""P2-D self-improving loop: pattern detection, auto_learn persistence, scoring nudges."""

from __future__ import annotations

from engine.config import Criteria
from engine.db.models import DB
from engine.learning.patterns import detect
from engine.learning.runner import auto_learn
from engine.scoring.fit import score_job


def test_detect_patterns_from_outcomes():
    outcomes = [
        {
            "final_state": "offer",
            "offer_made": 1,
            "recruiter_source": "referral",
            "interview_count": 2,
            "response_days": 5,
        },
        {
            "final_state": "interviewed",
            "recruiter_source": "referral",
            "interview_count": 1,
            "response_days": 7,
        },
        {"final_state": "rejected", "recruiter_source": "cold", "response_days": 10},
    ]
    kinds = {p[0] for p in detect(outcomes)}
    assert {"rejection_rate", "offer_rate", "referral_conversion", "process_speed"} <= kinds


def test_auto_learn_persists_and_is_idempotent(tmp_path):
    db = DB(tmp_path / "a.db")
    try:
        for st in ("offer", "rejected"):
            db.record_outcome(
                None,  # no real job row in this unit test; job_id is nullable
                "Acme Inc",
                final_state=st,
                recruiter_source="referral",
                offer_made=(st == "offer"),
                interview_count=1 if st == "offer" else 0,
            )
        n1 = auto_learn(db, "Acme")  # norm_company drops "inc" → same company
        n2 = auto_learn(db, "Acme Inc")
        assert n1 == n2 and n1 > 0
        kinds = {learning["pattern_type"] for learning in db.learnings_for_company("acme")}
        assert {"rejection_rate", "offer_rate"} <= kinds
    finally:
        db.close()


def test_score_job_applies_high_confidence_learning_only():
    crit = Criteria(roles=["data scientist"], remote_required=False)
    job = {"title": "Senior Data Scientist", "description": "python sql", "company": "Acme"}
    base = score_job(job, crit)
    boosted = score_job(
        job,
        crit,
        [{"pattern_type": "offer_rate", "observation": "Oferta en 3/4", "confidence": 0.9}],
    )
    assert boosted.score > base.score
    low = score_job(
        job, crit, [{"pattern_type": "offer_rate", "observation": "x", "confidence": 0.3}]
    )
    assert low.score == base.score  # below confidence gate → ignored


def test_rejection_rate_learning_is_informational_not_a_penalty():
    crit = Criteria(roles=["data scientist"], remote_required=False)
    job = {"title": "Senior Data Scientist", "description": "python sql", "company": "Acme"}
    base = score_job(job, crit)
    # A 0-rejection (or any rejection_rate) learning must NOT lower the score — only inform.
    with_rej = score_job(
        job,
        crit,
        [
            {
                "pattern_type": "rejection_rate",
                "observation": "Rechazo en 0/4 casos",
                "confidence": 0.9,
            }
        ],
    )
    assert with_rej.score == base.score
    assert any("Rechazo" in r for r in with_rej.reasons)


def test_feedback_disagree_halves_confidence(tmp_path):
    db = DB(tmp_path / "b.db")
    try:
        db.upsert_learning("Acme", "offer_rate", "Oferta en 3/3", 0.8, 3)
        lid = db.learnings_for_company("Acme")[0]["id"]
        db.record_learning_feedback(lid, feedback_type="disagree", reasoning="muestra chica")
        assert db.learnings_for_company("Acme")[0]["confidence"] == 0.4
    finally:
        db.close()
