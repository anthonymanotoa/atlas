"""Upskill / gap analysis — pass 1 (deterministic). Pass 2 (LLM synthesis) lives in the brain.

Pass 1 diffs each in-scope job's JD keywords against the master CV using the SAME gazetteer
as the tailor (engine/cv/match), and weights every missing skill by how BADLY the candidate
fits that job: score += (100 − fit_score)/100. Jobs you barely qualify for push their gaps to
the top — those are the skills that would unlock the most closed doors. The brain reads this
context and writes the study plan + severity heatmap; it never re-derives the numbers.

$0 invariant: this module is pure Python — ontology/keyword diff + arithmetic weighting. No
LLM, no API key. The brain does the synthesis (brain/prompts/upskill.md); the writer only
validates + persists it.
"""

from __future__ import annotations

import engine.paths as paths  # noqa: F401  (kept explicit so profile switches are followed)
from engine.config import load_master_cv, load_ontology
from engine.cv.match import match_score
from engine.db.models import DB
from engine.normalize import now_iso


def hard_skill_gaps(db: DB, states: list[str]) -> dict:
    """Weighted missing-skill inventory over the jobs in `states` (deterministic pass 1).

    Returns ``{"skills": [...], "jobs_considered": int, "generated_at": str}`` where each skill
    entry is ``{"skill", "score", "occurrences", "worst_fit", "jobs"}`` and ``skills`` is sorted
    by ``score`` descending. ``score`` accumulates ``(100 − fit_score)/100`` per job that both
    requires the skill and the CV does not evidence — so a skill demanded by a job you fit badly
    outranks the same skill demanded by a job you fit well. A job with no fit_score contributes
    weight 0 (a missing score is NOT treated as a low fit).
    """
    master = load_master_cv()
    ontology = load_ontology()
    agg: dict[str, dict] = {}
    considered = 0
    # de-dup across overlapping states (a job could match more than one requested state slice)
    seen_jobs: set[str] = set()
    for state in states:
        for job in db.list_jobs(state=state):
            if job["id"] in seen_jobs:
                continue
            seen_jobs.add(job["id"])
            considered += 1
            fit = job.get("fit_score")
            fit = 100.0 if fit is None else float(fit)
            weight = max(0.0, (100.0 - fit) / 100.0)
            for skill in match_score(job, master, ontology).missing:
                bucket = agg.setdefault(
                    skill,
                    {
                        "skill": skill,
                        "score": 0.0,
                        "occurrences": 0,
                        "worst_fit": fit,
                        "jobs": [],
                    },
                )
                bucket["score"] += weight
                bucket["occurrences"] += 1
                bucket["worst_fit"] = min(bucket["worst_fit"], fit)
                bucket["jobs"].append(job["id"])
    skills = sorted(agg.values(), key=lambda s: s["score"], reverse=True)
    for s in skills:
        s["score"] = round(s["score"], 4)
        s["jobs"] = s["jobs"][:10]  # cap the context payload
    return {"skills": skills, "jobs_considered": considered, "generated_at": now_iso()}
