"""Repost/ghost-job detection (spec §5.3): same company + fuzzy-equal title, distinct ids."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job
from engine.reposts import core_title, sweep_reposts
from engine.scoring.fit import score_job


def test_core_title_strips_seniority_and_modality():
    assert core_title("Senior Data Engineer (Remote)") == "data engineer"
    assert core_title("Data Engineer II - Hybrid") == "data engineer"
    assert core_title("Staff Data Engineer") == "data engineer"


def test_core_title_collapses_modality_variants_to_same_core():
    # The whole point: a repost under a new modality/seniority is the SAME core role.
    assert core_title("Senior Data Engineer (Remote)") == core_title("Data Engineer")


def test_core_title_title_of_only_stripped_tokens_is_empty():
    # A title made purely of seniority/modality words has no role identity → "".
    assert core_title("Senior (Remote)") == ""


def test_sweep_flags_fuzzy_equal_titles_same_company(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        # Distinct natural keys (different locations) → distinct rows, same core identity.
        db.upsert_job(
            Job(
                source="greenhouse", title="Senior Data Engineer", company="Acme", location="Remote"
            )
        )
        db.upsert_job(
            Job(
                source="lever",
                title="Data Engineer (Remote)",
                company="Acme Inc",
                location="Berlin",
            )
        )
        db.upsert_job(
            Job(source="lever", title="Backend Engineer", company="Other Co", location="Remote")
        )
        flagged = sweep_reposts(db)
        rows = {r["title"]: r for r in db.list_jobs()}
    assert flagged == 2
    assert rows["Senior Data Engineer"]["repost_count"] == 1
    assert rows["Data Engineer (Remote)"]["repost_count"] == 1
    assert rows["Backend Engineer"]["repost_count"] == 0


def test_sweep_leaves_unique_job_unflagged(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(source="greenhouse", title="Data Engineer", company="Acme", location="Remote")
        )
        flagged = sweep_reposts(db)
        rows = db.list_jobs()
    assert flagged == 0
    assert rows[0]["repost_count"] == 0


def test_sweep_ignores_postings_more_than_90_days_apart(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(source="greenhouse", title="Data Engineer", company="Acme", location="Remote")
        )
        db.upsert_job(
            Job(source="lever", title="Data Engineer (Remote)", company="Acme", location="Berlin")
        )
        # Age the second Acme posting past the window: it must NOT count with the fresh one.
        stale = (datetime.now(UTC) - timedelta(days=120)).isoformat()
        db.conn.execute(
            "UPDATE jobs SET discovered_at=? WHERE company='Acme' AND location='Berlin'", (stale,)
        )
        db.conn.commit()
        flagged = sweep_reposts(db)
        rows = {r["title"]: r for r in db.list_jobs()}
    assert flagged == 0
    # Only the fresh row is inside the window → group of 1 → no repost flag.
    assert rows["Data Engineer"]["repost_count"] == 0


def test_repost_penalty_and_flag_in_scoring():
    crit = Criteria(roles=["data engineer"], remote_required=False)
    base = {"title": "Data Engineer", "description": "python"}
    clean = score_job({**base, "repost_count": 0}, crit)
    reposted = score_job({**base, "repost_count": 2}, crit)
    assert clean.score - reposted.score == 4.0
    assert any(k.startswith("repost (") for k in reposted.knockouts)
    assert reposted.disqualified is False


def test_missing_repost_count_key_no_penalty():
    # Pre-F2 rows have no repost_count key at all → scored as a clean job.
    crit = Criteria(roles=["data engineer"], remote_required=False)
    base = {"title": "Data Engineer", "description": "python"}
    clean = score_job({**base, "repost_count": 0}, crit)
    absent = score_job(base, crit)
    assert absent.score == clean.score
    assert not any(k.startswith("repost (") for k in absent.knockouts)
