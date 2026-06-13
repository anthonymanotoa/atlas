"""Scoring orchestration shared by `atlas score` and the brain."""
from __future__ import annotations

from engine.config import Criteria
from engine.db.models import DB
from engine.scoring.fit import score_job


def score_jobs(db: DB, criteria: Criteria, *, rescore: bool = False) -> tuple[int, int]:
    """Score jobs and shortlist those above threshold. Returns (scored, shortlisted).

    rescore re-evaluates only EARLY-stage jobs (discovered/scored/shortlisted) so it never
    regresses a job that has already been tailored, made ready, applied to, etc.
    """
    if rescore:
        jobs = db.list_jobs(states=["discovered", "scored", "shortlisted"])
    else:
        jobs = db.list_jobs(state="discovered")
    scored = shortlisted = 0
    for j in jobs:
        res = score_job(j, criteria)
        db.set_fit(j["id"], res.score, res.reasons, res.knockouts)
        db.set_state(j["id"], "scored")          # always stamp scored_at (funnel accuracy)
        scored += 1
        if res.score >= criteria.shortlist_threshold and not res.disqualified:
            db.set_state(j["id"], "shortlisted")
            shortlisted += 1
    return scored, shortlisted
