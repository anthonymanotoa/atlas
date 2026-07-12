"""--rescore geo cleanup: re-extract stored scopes and demote newly-ineligible pre-send jobs.

Fictional candidate in Ecuador ("ec" as an EXAMPLE value; the code default is "" = off).
"""

from __future__ import annotations

import json

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job
from engine.scoring.run import score_jobs


def _crit() -> Criteria:
    return Criteria(
        roles=["data scientist"],
        remote_required=True,
        candidate_country="ec",
        acceptable_regions=["worldwide", "latam"],
        shortlist_threshold=62.0,
    )


def _seed(db: DB, location: str, *, title: str = "Senior Data Scientist") -> str:
    db.upsert_job(
        Job(
            source="test",
            title=title,
            company="Acme",
            location=location,
            is_remote=True,
            description="SQL and Python.",
        ).finalize()
    )
    return next(j["id"] for j in db.list_jobs() if j["title"] == title)


def test_rescore_reextracts_and_persists_stale_geo(tmp_path):
    with DB(tmp_path / "t.db") as db:
        jid = _seed(db, "Remote — CO, US")
        db.set_geo(jid, "CO, US", "us,co")  # simulate a stale scope from the old extractor
        db.set_state(jid, "scored")
        score_jobs(db, _crit(), rescore=True)
        row = db.get_job(jid)
    assert row["geo_scope"] == "us"  # collision repaired on rescore
    assert row["state"] == "scored"  # us-only → disqualified → not shortlisted


def test_rescore_demotes_newly_disqualified_ready_job(tmp_path):
    with DB(tmp_path / "t.db") as db:
        jid = _seed(db, "Remote — MN, US")
        for s in ("scored", "shortlisted", "tailored", "ready"):
            db.set_state(jid, s)
        score_jobs(db, _crit(), rescore=True)
        row = db.get_job(jid)
    assert row["state"] == "scored"  # pulled out of the ready column
    assert any("remoto solo US" in k for k in json.loads(row["knockout_flags"]))


def test_rescore_leaves_eligible_ready_job_untouched(tmp_path):
    with DB(tmp_path / "t.db") as db:
        jid = _seed(db, "Remote LatAm")
        for s in ("scored", "shortlisted", "tailored", "ready"):
            db.set_state(jid, s)
        score_jobs(db, _crit(), rescore=True)
        row = db.get_job(jid)
    assert row["geo_scope"] == "latam"
    assert row["state"] == "ready"  # still eligible → never regressed
