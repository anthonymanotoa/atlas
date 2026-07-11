"""Collapse near-identical shortlist postings (Task 9).

The audit found the same role re-posted under a handful of ids ("Data Analyst",
"Data Analyst II", "Senior Data Analyst"...) flooding the top of the shortlist. Reposts are
already flagged at discovery (`jobs.repost_count`, `engine/reposts.py::sweep_reposts`), but
nothing COLLAPSES them into one row. This module groups by the exact same key the repost
detector uses — `(norm_company(company), core_title(title))` — so a job counted as a repost
is also the job that gets collapsed.
"""

from __future__ import annotations

from engine.normalize import norm_company, parse_dt_utc
from engine.reposts import core_title

_MIN_FIT = float("-inf")


def _fit(job: dict) -> float:
    score = job.get("fit_score")
    return _MIN_FIT if score is None else float(score)


def _discovered(job: dict):
    # parse_dt_utc returns an aware datetime or None (garbage/missing); treat missing as the
    # oldest possible so a job with no timestamp never wins a tie-break it has no evidence for.
    dt = parse_dt_utc(job.get("discovered_at"))
    return dt or parse_dt_utc("1970-01-01T00:00:00+00:00")


def collapse_variants(jobs: list[dict]) -> list[dict]:
    """Collapse near-identical postings (same norm_company + core_title) into one canonical
    job per group. Canonical = highest fit_score, tie-break most recent (discovered_at).
    Each returned job gets variant_count: int (>=1) and variant_ids: list[str] (all ids in
    the group incl. canonical, canonical first). Order of groups preserves the input order
    of their canonical job."""
    groups: dict[tuple[str, str], list[dict]] = {}
    order: list[tuple[str, str]] = []
    for job in jobs:
        key = (norm_company(job.get("company")), core_title(job.get("title") or ""))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(job)

    out: list[dict] = []
    for key in order:
        members = groups[key]
        # Highest fit wins; ties broken by most recent discovered_at.
        canonical = max(members, key=lambda j: (_fit(j), _discovered(j)))
        variant_ids = [canonical["id"]] + [
            m["id"] for m in members if m is not canonical
        ]
        result = dict(canonical)
        result["variant_count"] = len(members)
        result["variant_ids"] = variant_ids
        out.append(result)
    return out
