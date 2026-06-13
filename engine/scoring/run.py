"""Scoring orchestration shared by `atlas score` and the brain."""

from __future__ import annotations

from collections import defaultdict

from engine.config import Criteria, load_master_cv, load_ontology
from engine.cv.match import match_score
from engine.db.models import DB
from engine.normalize import norm_company
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
    # Load per-company learnings once (P2-D) so the scorer can nudge by past outcomes.
    learn_map: dict[str, list[dict]] = defaultdict(list)
    for learning in db.all_learnings():
        learn_map[learning["company"]].append(learning)
    # Load CV + skills ontology once for the CV↔JD match score (cheap per-job, no DOCX render).
    master = load_master_cv()
    ontology = load_ontology()
    have_cv = bool(master and ontology)
    scored = shortlisted = 0
    for j in jobs:
        res = score_job(j, criteria, learn_map.get(norm_company(j.get("company", ""))))
        db.set_fit(j["id"], res.score, res.reasons, res.knockouts)
        if have_cv:
            m = match_score(j, master, ontology)
            db.set_match(j["id"], m.score, m.missing)
        db.set_state(j["id"], "scored")  # always stamp scored_at (funnel accuracy)
        scored += 1
        if res.score >= criteria.shortlist_threshold and not res.disqualified:
            db.set_state(j["id"], "shortlisted")
            shortlisted += 1
    return scored, shortlisted
