"""Re-apply window (spec §5.3): flag — never hide — companies with a recent own application.

The flag is INFORMATIVE ONLY: discovery keeps showing these jobs and the score is untouched;
the scorer only appends a knockout/reason so you don't burn a fresh application too soon.
`re_apply_window_days=0` (the default) turns the feature off entirely.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job
from engine.scoring.run import _recently_applied_companies, score_jobs


def _seed(db: DB, title: str, company: str, applied: bool = False) -> str:
    db.upsert_job(Job(source="lever", title=title, company=company, description="python data"))
    jid = next(j["id"] for j in db.list_jobs() if j["title"] == title)
    if applied:
        db.set_state(jid, "applied")
    return jid


def _set_applied_at(db: DB, job_id: str, days_ago: float) -> None:
    """Deterministically stamp jobs.applied_at to exactly `days_ago` (avoids now()-flakiness)."""
    ts = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    db.conn.execute("UPDATE jobs SET applied_at=? WHERE id=?", (ts, job_id))
    db.conn.commit()


def test_recently_applied_companies_windowing(tmp_path):
    with DB(tmp_path / "a.db") as db:
        _seed(db, "Data Engineer", "Acme Inc", applied=True)
        _seed(db, "ML Engineer", "Other Co")
        recent = _recently_applied_companies(db, 14)
    assert "acme" in recent and recent["acme"] == 0  # applied today → 0 days ago
    assert "other co" not in recent  # never applied → absent


def test_recently_applied_companies_off_when_window_zero(tmp_path):
    with DB(tmp_path / "a.db") as db:
        _seed(db, "Data Engineer", "Acme", applied=True)
        assert _recently_applied_companies(db, 0) == {}  # window=0 → OFF, empty map


def test_application_inside_window_is_included(tmp_path):
    with DB(tmp_path / "a.db") as db:
        jid = _seed(db, "Data Engineer", "Acme", applied=True)
        _set_applied_at(db, jid, days_ago=5)
        recent = _recently_applied_companies(db, 30)
    assert recent.get("acme") == 5  # 5 days ago, window 30 → present with 5


def test_application_outside_window_is_excluded(tmp_path):
    with DB(tmp_path / "a.db") as db:
        jid = _seed(db, "Data Engineer", "Acme", applied=True)
        _set_applied_at(db, jid, days_ago=60)
        recent = _recently_applied_companies(db, 30)
    assert "acme" not in recent  # 60 days ago, window 30 → outside, excluded


def test_new_job_at_recently_applied_company_gets_flag(tmp_path):
    crit = Criteria(roles=["data engineer"], remote_required=False, re_apply_window_days=14)
    with DB(tmp_path / "a.db") as db:
        applied_id = _seed(db, "Data Engineer", "Acme", applied=True)
        _set_applied_at(db, applied_id, days_ago=5)
        fresh = _seed(db, "Senior Data Engineer", "Acme")
        score_jobs(db, crit)
        row = db.get_job(fresh)
        flags = json.loads(row["knockout_flags"] or "[]")
        applied_row = db.get_job(applied_id)
    assert any(f.startswith("aplicaste a esta empresa hace") for f in flags)
    assert "5 días" in " ".join(flags)  # reports the real days-ago
    assert applied_row["state"] == "applied"  # the applied job itself is never re-flagged/rescored


def test_flag_is_informative_only_no_score_change(tmp_path):
    """Same fresh job scored with vs without a recent own application → identical score."""
    with DB(tmp_path / "base.db") as db:
        base_id = _seed(db, "Senior Data Engineer", "Acme")
        score_jobs(db, Criteria(roles=["data engineer"], remote_required=False))
        base_score = db.get_job(base_id)["fit_score"]
    with DB(tmp_path / "flagged.db") as db:
        applied_id = _seed(db, "Data Engineer", "Acme", applied=True)
        _set_applied_at(db, applied_id, days_ago=5)
        fresh = _seed(db, "Senior Data Engineer", "Acme")
        score_jobs(
            db, Criteria(roles=["data engineer"], remote_required=False, re_apply_window_days=14)
        )
        flagged = db.get_job(fresh)
    assert flagged["fit_score"] == base_score  # flag never moves the score
    assert flagged["state"] != "dismissed"  # never disqualified/hidden by the flag


def test_never_applied_company_gets_no_flag(tmp_path):
    crit = Criteria(roles=["data engineer"], remote_required=False, re_apply_window_days=14)
    with DB(tmp_path / "a.db") as db:
        _seed(db, "Data Engineer", "Acme", applied=True)  # applied to Acme, not to Other Co
        fresh = _seed(db, "Data Scientist", "Other Co")
        score_jobs(db, crit)
        flags = json.loads(db.get_job(fresh)["knockout_flags"] or "[]")
    assert not any(f.startswith("aplicaste a") for f in flags)


def test_outside_window_job_gets_no_flag(tmp_path):
    crit = Criteria(roles=["data engineer"], remote_required=False, re_apply_window_days=30)
    with DB(tmp_path / "a.db") as db:
        applied_id = _seed(db, "Data Engineer", "Acme", applied=True)
        _set_applied_at(db, applied_id, days_ago=60)  # outside the 30-day window
        fresh = _seed(db, "Senior Data Engineer", "Acme")
        score_jobs(db, crit)
        flags = json.loads(db.get_job(fresh)["knockout_flags"] or "[]")
    assert not any(f.startswith("aplicaste a") for f in flags)


def test_window_off_by_default(tmp_path):
    crit = Criteria(roles=["data engineer"], remote_required=False)  # re_apply_window_days=0
    with DB(tmp_path / "a.db") as db:
        _seed(db, "Data Engineer", "Acme", applied=True)
        fresh = _seed(db, "Senior Data Engineer", "Acme")
        score_jobs(db, crit)
        flags = json.loads(db.get_job(fresh)["knockout_flags"] or "[]")
    assert not any(f.startswith("aplicaste a") for f in flags)
