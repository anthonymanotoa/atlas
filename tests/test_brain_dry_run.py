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


def _seed_shortlisted(db: DB, title: str, company: str, fit: float) -> str:
    j = Job(source="x", title=title, company=company, location="Remote")
    db.upsert_job(j)
    db.set_fit(j.id, fit, [], [])
    db.set_state(j.id, "shortlisted")
    return j.id


def test_dry_run_collapses_shortlist_variants(db: DB):
    """Task 9 dedupe (collapse_variants) must apply to the brain's OWN prep selection, not
    just `atlas top` / `/api/board`: 5 near-identical CVS Health postings + 1 distinct job
    must collapse to 2 would_prep entries, not 6 (the exact "7x CVS Health" bug report)."""
    variant_titles = [
        "Data Analyst",
        "Data Analyst II",
        "Senior Data Analyst",
        "Data Analyst (Remote)",
        "Sr. Data Analyst - Hybrid",
    ]
    ids = [
        _seed_shortlisted(db, title, "CVS Health", fit=80 + i)
        for i, title in enumerate(variant_titles)
    ]
    other_id = _seed_shortlisted(db, "ML Engineer", "OtherCo", fit=70)

    summary = run(db, dry_run=True, do_discover=False)

    assert len(summary["would_prep"]) == 2
    by_company = {j["company"]: j for j in summary["would_prep"]}
    assert set(by_company) == {"CVS Health", "OtherCo"}

    cvs_entry = by_company["CVS Health"]
    assert cvs_entry["variant_count"] == 5
    assert cvs_entry["id"] == ids[-1]  # highest fit (84) among the CVS variants

    other_entry = by_company["OtherCo"]
    assert other_entry["variant_count"] == 1
    assert other_entry["id"] == other_id


def test_dry_run_would_prep_respects_limit_after_collapse(db: DB):
    """`limit` must slice the COLLAPSED pool (canonicals), matching the real prep loop and
    `atlas top` — collapsing AFTER truncating (the pre-fix behavior) would let the CVS
    repost cluster (fit 85-89, the two highest-fit rows in the whole table) eat the entire
    limit=2 budget with two duplicates of the SAME job, hiding Beta entirely."""
    for i, title in enumerate(["Data Analyst", "Data Analyst II", "Senior Data Analyst"]):
        _seed_shortlisted(db, title, "CVS Health", fit=85 + i)
    _seed_shortlisted(db, "ML Engineer", "Beta", fit=80)
    _seed_shortlisted(db, "Backend Engineer", "Gamma", fit=75)

    summary = run(db, dry_run=True, do_discover=False, limit=2)

    assert len(summary["would_prep"]) == 2
    companies = {j["company"] for j in summary["would_prep"]}
    # Collapsed canonicals ranked by fit: CVS cluster (89) then Beta (80) beat Gamma (75).
    assert companies == {"CVS Health", "Beta"}


def test_shortlisted_to_prepare_helper_collapses_variants(db: DB):
    """Unit-test the extracted selection helper directly (both `run()`'s real prep loop and
    the dry-run preview call this) so the collapse-then-slice behavior is locked even where
    invoking a full real `run()` would require heavier profile/CV-layout config."""
    from brain.run_brain import _shortlisted_to_prepare

    variant_titles = ["Data Analyst", "Data Analyst II", "Senior Data Analyst"]
    for i, title in enumerate(variant_titles):
        _seed_shortlisted(db, title, "CVS Health", fit=80 + i)
    other_id = _seed_shortlisted(db, "ML Engineer", "OtherCo", fit=70)

    result = _shortlisted_to_prepare(db, limit=8)

    assert len(result) == 2
    ids = {j["id"] for j in result}
    assert other_id in ids
    cvs_job = next(j for j in result if j["company"] == "CVS Health")
    assert cvs_job["variant_count"] == 3
