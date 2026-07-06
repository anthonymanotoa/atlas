"""Scoring orchestration shared by `atlas score` and the brain."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from engine.config import Criteria, load_master_cv, load_ontology
from engine.cv.match import match_score
from engine.db.models import DB
from engine.knockouts import prescan
from engine.normalize import norm_company
from engine.scoring.fit import score_job


def _recently_applied_companies(db: DB, window_days: int) -> dict[str, int]:
    """norm_company → days since YOUR most recent application to it, within the window.

    Powers the re-apply window (F2): discovery keeps showing these jobs, the scorer only
    FLAGS them ("aplicaste hace N días") so you don't burn a fresh application too soon.
    Reads jobs.applied_at (stamped by set_state(..., "applied")); window_days<=0 → OFF.
    """
    if window_days <= 0:
        return {}
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    out: dict[str, int] = {}
    rows = db.conn.execute(
        "SELECT company, applied_at FROM jobs WHERE applied_at IS NOT NULL"
    ).fetchall()
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["applied_at"])
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if dt < cutoff:
            continue
        days = int((now - dt).total_seconds() // 86400)
        comp = norm_company(r["company"])
        if comp and (comp not in out or days < out[comp]):
            out[comp] = days
    return out


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
    # F2 re-apply window: fetch the applied-companies map ONCE per run (never per-job) so an
    # informative flag can be attached below. Empty when re_apply_window_days=0 (feature off).
    recent_applied = _recently_applied_companies(db, criteria.re_apply_window_days)
    # Load CV + skills ontology once for the CV↔JD match score (cheap per-job, no DOCX render).
    master = load_master_cv()
    ontology = load_ontology()
    have_cv = bool(master and ontology)
    scored = shortlisted = 0
    for j in jobs:
        res = score_job(j, criteria, learn_map.get(norm_company(j.get("company", ""))))
        # F2 re-apply window (informative only — no score change, no DQ): flag a fresh job at a
        # company you applied to <window days ago. Skip the applied job itself (has applied_at).
        if recent_applied and not j.get("applied_at"):
            days = recent_applied.get(norm_company(j.get("company", "")))
            if days is not None:
                res.knockouts.append(f"aplicaste a esta empresa hace {days} días")
                res.reasons.append(
                    f"re-apply window: own application {days}d ago "
                    f"(<{criteria.re_apply_window_days}d)"
                )
        warnings = prescan(j, criteria, master)
        db.set_fit(j["id"], res.score, res.reasons, res.knockouts, warnings=warnings)
        if have_cv:
            m = match_score(j, master, ontology)
            db.set_match(j["id"], m.score, m.missing)
        db.set_state(j["id"], "scored")  # always stamp scored_at (funnel accuracy)
        scored += 1
        if res.score >= criteria.shortlist_threshold and not res.disqualified:
            db.set_state(j["id"], "shortlisted")
            shortlisted += 1
    return scored, shortlisted
