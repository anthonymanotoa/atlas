"""F3 §6.5: machine summary — deltas por factor en el score, persistidos por corrida."""

from __future__ import annotations

import json
from pathlib import Path

from engine.config import Criteria
from engine.scoring.fit import score_job

CRIT = Criteria(roles=["data scientist"], remote_required=True, must_haves=["python"],
                salary_floor_usd=70000)

JOB = {"title": "Senior Data Scientist", "company": "Acme", "is_remote": 1,
       "workplace_type": "remote", "salary_min": 90000, "salary_max": 120000,
       "salary_interval": "yearly", "description": "We use python and sql daily."}


def test_score_job_records_factor_deltas():
    res = score_job(JOB, CRIT)
    factors = {f["factor"]: f for f in res.factors}
    assert factors["role"]["delta"] == 25
    assert factors["remote"]["delta"] == 15
    assert factors["salary"]["delta"] == 10
    assert all({"factor", "delta", "note"} <= set(f) for f in res.factors)


def test_deltas_sum_to_final_score_when_unclamped():
    # A genuinely-unclamped job: role no-match (-35, title/desc never say "data scientist") +
    # remote (+15) + must-have python (+4) = 50-16 = 34, comfortably inside the 0–100 bound with no
    # soft-cap/disq firing, so base + Σdeltas == final (the point of this reconciliation test).
    job = {"title": "Analytics Engineer", "company": "Acme", "is_remote": 1,
           "workplace_type": "remote", "description": "We use python for data science work."}
    res = score_job(job, CRIT)
    assert res.score == 50.0 + sum(f["delta"] for f in res.factors)


def test_upper_clamp_documented_not_reconciled():
    # The base JOB fixture raw-sums to 50+64=114 but the 0–100 bound caps it at 100. Adding the
    # breakdown must NOT change that score (pure observability), and the clamp is surfaced via the
    # base/final gap — the deltas deliberately do NOT reconcile to final here (that IS the clamp).
    res = score_job(JOB, CRIT)
    raw = 50.0 + sum(f["delta"] for f in res.factors)
    assert res.score == 100.0  # unchanged by instrumentation (pre-existing upper clamp)
    assert raw == 114.0 and raw > res.score  # clamp is real and visible in the breakdown
    b = res.breakdown()
    assert b["base"] == 50.0 and b["final"] == 100.0


def test_breakdown_shape():
    b = score_job(JOB, CRIT).breakdown()
    assert b["base"] == 50.0 and b["final"] == score_job(JOB, CRIT).score
    assert b["disqualified"] is False and isinstance(b["factors"], list)
    assert b["reasons"] and b["knockouts"] == []


def test_negative_factor_recorded():
    res = score_job({**JOB, "title": "Senior Underwater Basket Weaver",
                     "description": "no relevant terms"}, CRIT)
    factors = {f["factor"]: f for f in res.factors}
    assert factors["role"]["delta"] == -35


def test_breakdown_persisted_and_exposed(tmp_path: Path, monkeypatch):
    from engine import analytics
    from engine.db.models import DB
    from engine.normalize import Job
    from engine.scoring.run import score_jobs

    monkeypatch.setattr("engine.scoring.run.load_master_cv", lambda: {})
    monkeypatch.setattr("engine.scoring.run.load_ontology", lambda: {})
    db = DB(tmp_path / "t.db")
    db.upsert_job(Job(source="greenhouse", title="Senior Data Scientist", company="Acme",
                      location="Remote", is_remote=True, description="python everywhere"))
    score_jobs(db, CRIT)
    row = db.list_jobs()[0]
    stored = json.loads(row["score_breakdown"])
    assert stored["final"] == row["fit_score"] and stored["factors"]
    detail = analytics.job_detail(db, row["id"])
    assert detail["job"]["score_breakdown"]["base"] == 50.0
