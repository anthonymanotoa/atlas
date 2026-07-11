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
    index_of: dict[int, int] = {id(job): i for i, job in enumerate(jobs)}

    groups: dict[tuple[str, str] | int, list[dict]] = {}
    order: list[tuple[str, str] | int] = []
    for job in jobs:
        core = core_title(job.get("title") or "")
        if core:
            key: tuple[str, str] | int = (norm_company(job.get("company")), core)
        else:
            # A title made only of stripped tokens (e.g. "Senior", "Remote") has no role
            # identity — mirrors the `if key[1]:` guard in sweep_reposts (engine/reposts.py).
            # Force it into its own singleton group instead of merging on the empty core.
            key = id(job)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(job)

    built: list[tuple[int, dict]] = []
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
        built.append((index_of[id(canonical)], result))

    # Group order preserves the input order of their canonical job, not the group's
    # first-encountered member (those can differ when the canonical isn't first-appearing).
    built.sort(key=lambda pair: pair[0])
    return [result for _, result in built]
