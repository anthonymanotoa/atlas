"""F3 §6.1: cadencia por estado, seed idempotente, buckets URGENT/OVERDUE/waiting/COLD, drafts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job
from engine.outreach import followups as fu


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


CRIT = Criteria(roles=["data scientist"])


def _seed_job(db: DB, state: str = "applied") -> str:
    db.upsert_job(
        Job(source="greenhouse", title="Data Scientist", company="Acme", location="Remote")
    )
    jid = db.list_jobs()[0]["id"]
    db.set_state(jid, state, {"via": "test"})
    return jid


def test_cadence_for_reads_criteria_defaults():
    assert fu.cadence_for("applied", CRIT) == (7, 2)
    assert fu.cadence_for("responded", CRIT) == (1, 1)
    assert fu.cadence_for("interview", CRIT) == (1, 1)
    assert fu.cadence_for("shortlisted", CRIT) is None


def test_seed_for_state_creates_first_touch_at_plus_days(db: DB):
    jid = _seed_job(db)
    base = "2026-07-04T12:00:00+00:00"
    fid = fu.seed_for_state(db, jid, "applied", CRIT, base_iso=base)
    assert fid is not None
    rows = db.followups_for_job(jid)
    assert len(rows) == 1
    assert rows[0]["kind"] == "applied" and rows[0]["touch_number"] == 1
    assert rows[0]["due_at"].startswith("2026-07-11")  # +7d


def test_seed_for_state_is_idempotent_while_pending(db: DB):
    jid = _seed_job(db)
    assert fu.seed_for_state(db, jid, "applied", CRIT) is not None
    assert fu.seed_for_state(db, jid, "applied", CRIT) is None  # re-run: no duplica
    assert len(db.followups_for_job(jid)) == 1


def test_register_sent_seeds_next_touch_until_cap(db: DB):
    jid = _seed_job(db)
    f1 = fu.seed_for_state(db, jid, "applied", CRIT)
    r1 = fu.register_sent(db, f1, CRIT)
    assert r1["ok"] is True and r1["next_id"] is not None  # touch 2 sembrado (max 2)
    r2 = fu.register_sent(db, r1["next_id"], CRIT)
    assert r2["ok"] is True and r2["next_id"] is None  # cap alcanzado → COLD después
    rows = db.followups_for_job(jid)
    assert sorted(f["touch_number"] for f in rows) == [1, 2]
    assert all(f["state"] == "done" for f in rows)


def test_register_sent_unknown_id(db: DB):
    assert fu.register_sent(db, 99999, CRIT) == {"ok": False, "next_id": None}


def test_bucket_followups_pure_classification():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)

    def mk(days: int) -> dict:
        return {"id": 1, "state": "pending", "due_at": (now + timedelta(days=days)).isoformat()}

    b = fu.bucket_followups([mk(2), mk(-1), mk(-5), {**mk(-1), "state": "done"}], now)
    assert [len(b["waiting"]), len(b["urgent"]), len(b["overdue"])] == [1, 1, 1]  # done se ignora
    assert b["urgent"][0]["days_overdue"] == 1.0
    assert b["overdue"][0]["days_overdue"] == 5.0


def test_cold_jobs_detects_exhausted_cadence(db: DB):
    jid = _seed_job(db)
    f1 = fu.seed_for_state(db, jid, "applied", CRIT, base_iso="2026-06-01T00:00:00+00:00")
    assert fu.cold_jobs(db, CRIT) == []  # aún hay pending
    nxt = fu.register_sent(db, f1, CRIT)["next_id"]
    fu.register_sent(db, nxt, CRIT)
    cold = fu.cold_jobs(db, CRIT)
    assert len(cold) == 1 and cold[0]["job_id"] == jid and cold[0]["touches_done"] == 2


def test_drafts_obey_rules_all_kinds_and_languages():
    job = {"company": "Acme", "title": "Data Scientist"}
    for kind in ("applied", "responded", "interview"):
        for lang in ("en", "es"):
            d = fu.draft_followup(job, "Jane Doe", kind, 1, language=lang, highlight="churn models")
            assert "just checking in" not in d.body.lower()
            assert len(d.body.split()) < 150
            assert "Acme" in d.body and d.subject
            assert d.language == lang


def test_draft_second_touch_differs_from_first():
    job = {"company": "Acme", "title": "Data Scientist"}
    d1 = fu.draft_followup(job, "Jane", "applied", 1)
    d2 = fu.draft_followup(job, "Jane", "applied", 2)
    assert d1.body != d2.body and d2.variant == "applied-touch2"


def test_schedule_stores_aware_due_at_for_naive_base(db: DB):
    jid = _seed_job(db)
    fu.schedule(db, jid, channel="email", base_iso="2026-01-15T10:00:00")  # naive base_iso
    rows = db.followups_for_job(jid, "email")
    assert len(rows) == len(fu.CADENCE)
    for f in rows:
        assert datetime.fromisoformat(f["due_at"]).tzinfo is not None


def test_bucket_followups_naive_due_at_still_buckets():
    now = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    pending = {"id": 1, "state": "pending", "due_at": "2026-01-01"}  # bare date, naive
    b = fu.bucket_followups([pending], now)
    assert len(b["overdue"]) == 1
    assert b["overdue"][0]["days_overdue"] > 0
