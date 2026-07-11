"""Locks `brain.run_brain.run(dry_run=True)`: reads only, zero writes.

Seeds 2 shortlisted jobs + 1 discovered job, snapshots DB state, runs dry_run,
then asserts both the summary shape and that the DB is byte-for-byte unchanged
(same counts_by_state, no new events, no morning brief written).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.run_brain import run
from engine.db.models import DB
from engine.normalize import Job


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


def _event_count(db: DB) -> int:
    return int(db.conn.execute("SELECT COUNT(*) n FROM events").fetchone()["n"])


def test_dry_run_reports_without_writing(db: DB):
    # Seed 2 shortlisted jobs + 1 discovered job — same pattern as tests/test_engine.py.
    db.upsert_job(Job(source="x", title="DS One", company="Acme", location="Remote"))
    db.upsert_job(Job(source="x", title="DS Two", company="Beta", location="Remote"))
    db.upsert_job(Job(source="x", title="DS Three", company="Gamma", location="Remote"))
    jobs = db.list_jobs()
    assert len(jobs) == 3
    ids = [j["id"] for j in jobs]
    db.set_state(ids[0], "shortlisted")
    db.set_state(ids[1], "shortlisted")
    # ids[2] stays in the default "discovered" state.

    counts_before = db.counts_by_state()
    events_before = _event_count(db)

    summary = run(db, dry_run=True, do_discover=False)

    assert summary["dry_run"] is True
    assert summary["would_discover"] is False
    assert summary["would_score"] == 1  # the one job still in "discovered"
    assert len(summary["would_prep"]) == 2  # the two shortlisted jobs
    assert summary["pending_intents"] == 0

    prepped_ids = {j["id"] for j in summary["would_prep"]}
    assert prepped_ids == {ids[0], ids[1]}
    assert all(j["already_prepared"] is False for j in summary["would_prep"])

    # Zero writes: DB state is byte-for-byte unchanged.
    assert db.counts_by_state() == counts_before
    assert _event_count(db) == events_before
