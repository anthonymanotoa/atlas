"""Deterministic, explainable fit scoring (0–100) against the user's criteria.

Philosophy (from the research): the real ATS filters are knockout questions + human
triage, not a magic keyword score. So this scorer is a transparent pre-filter that
surfaces *reasons* and *knockout flags* — the Cowork brain does the nuanced ranking
of borderline matches. Deal-breakers cap the score; knockouts are flagged, not auto-rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from engine.config import Criteria
from engine.lang import detect_language
from engine.normalize import norm_company

# Senior IC track (good fit). NOTE: director/head/chief live in EXEC_TERMS, not here —
# they're over-qualified for an IC pivoting into AI, so they must NOT earn a seniority bonus.
SENIOR_TERMS = ("senior", "sr.", "sr ", "lead", "staff", "principal")
EXEC_TERMS = (
    "director",
    "vp ",
    "vp,",
    "vice president",
    "head of",
    "chief",
    " cto",
    " ceo",
    " cfo",
    " coo",
    "svp",
    "evp",
    "c-level",
    "managing director",
)
JUNIOR_TERMS = (
    "junior",
    "jr.",
    "jr ",
    "intern",
    "internship",
    "entry level",
    "entry-level",
    "graduate",
    "trainee",
    "becario",
    "practicante",
    "working student",
    "apprentice",
)

_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs|años)", re.I)


@dataclass
class ScoreResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    knockouts: list[str] = field(default_factory=list)
    disqualified: bool = False


def _has(hay: str, term: str) -> bool:
    return term.lower() in hay


def _age_days(job: dict) -> float | None:
    """Days since the posting went live (date_posted), falling back to when we found it."""
    raw = job.get("date_posted") or job.get("discovered_at")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        try:
            dt = datetime.strptime(str(raw)[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (datetime.now(UTC) - dt).total_seconds() / 86400


def _required_years(text: str) -> int | None:
    yrs = [int(m) for m in _YEARS.findall(text)]
    return max(yrs) if yrs else None


def score_job(job: dict, criteria: Criteria, learnings: list[dict] | None = None) -> ScoreResult:
    title = job.get("title") or ""
    title_l = title.lower()
    desc = job.get("description") or ""
    hay = f"{title_l} {desc.lower()}"

    score = 50.0
    reasons: list[str] = []
    knockouts: list[str] = []
    disq = False

    # 0. Company blocklist — never surface these (hard filter, short-circuits).
    if criteria.company_blocklist:
        blocked = {norm_company(c) for c in criteria.company_blocklist}
        if norm_company(job.get("company")) in blocked:
            return ScoreResult(0.0, ["company in blocklist"], ["company in blocklist"], True)

    # 1. Role relevance (strongest signal; title-weighted).
    role_terms = criteria.all_role_terms
    if any(_has(title_l, t) for t in role_terms):
        score += 25
        reasons.append("role matches title")
    elif any(_has(hay, t) for t in role_terms):
        score += 8
        reasons.append("role matches description only")
    else:
        score -= 35
        reasons.append("no role keyword match")

    # 2. Remote (hard requirement).
    is_remote = job.get("is_remote")
    wt = (job.get("workplace_type") or "unknown").lower()
    if criteria.remote_required:
        if is_remote == 1 or is_remote is True or wt == "remote":
            score += 15
            reasons.append("remote")
        elif is_remote in (0, False) or wt in ("onsite", "hybrid"):
            disq = True
            reasons.append(f"not remote ({wt})")
        else:
            reasons.append("remote status unknown")

    # 3. Seniority — junior is under-qualified (DQ); exec is over-qualified (DQ when excluded).
    title_pad = f" {title_l} "
    if any(_has(title_l, t) for t in JUNIOR_TERMS):
        disq = True
        reasons.append("junior/intern level (under-qualified)")
    elif criteria.exclude_exec and any(_has(title_pad, t) for t in EXEC_TERMS):
        disq = True
        knockouts.append("over-qualified (exec/management role)")
        reasons.append("exec/management title — over-qualified for an IC track")
    elif any(_has(title_l, t.strip()) for t in [s.strip() for s in criteria.seniority]) or any(
        _has(title_l, t) for t in SENIOR_TERMS
    ):
        score += 10
        reasons.append("seniority matches")

    # 4. Salary (soft unless criteria.salary_hard).
    smin, smax = job.get("salary_min"), job.get("salary_max")
    floor = criteria.salary_floor_usd
    if floor and (smin or smax):
        top = smax or smin
        interval = (job.get("salary_interval") or "yearly").lower()
        annual = top * {"hourly": 2080, "daily": 260, "weekly": 52, "monthly": 12, "yearly": 1}.get(
            interval, 1
        )
        if annual >= floor:
            score += 10
            reasons.append("salary meets floor")
        else:
            if criteria.salary_hard:
                disq = True
            score -= 10
            reasons.append("salary below floor")

    # 5. Must-haves.
    hits = [m for m in criteria.must_haves if _has(hay, m)]
    if hits:
        score += min(len(hits) * 4, 12)
        reasons.append(f"must-haves: {', '.join(hits)}")

    # 6. Deal-breakers (cap score).
    db_hits = [d for d in criteria.deal_breakers if _has(hay, d)]
    if db_hits:
        disq = True
        reasons.append(f"deal-breaker: {', '.join(db_hits)}")

    # 7. Knockouts (flag, don't reject).
    ko = [k for k in criteria.knockout_terms if _has(hay, k)]
    if ko:
        knockouts.extend(ko)
        score -= min(len(ko) * 5, 10)
        reasons.append(f"knockout flags: {', '.join(ko)}")

    # 8. Off-target language — use the language stored at discovery, else detect now.
    lang = job.get("language") or detect_language(desc or title)
    if lang and lang not in criteria.languages:
        score -= 25
        reasons.append(f"likely {lang}-language posting (off-target)")

    # 9. Freshness — relatively-new postings only; stale ones downranked (DQ if hard).
    if criteria.max_age_days:
        age = _age_days(job)
        if age is not None and age > criteria.max_age_days:
            score -= 15
            reasons.append(f"posted ~{age:.0f}d ago (stale, >{criteria.max_age_days}d)")
            if criteria.freshness_hard:
                disq = True

    # 10. Over-demanding experience requirement (flag, don't reject).
    if criteria.max_years_required and desc:
        req = _required_years(desc)
        if req and req > criteria.max_years_required:
            knockouts.append(f"requires {req}+ years")
            score -= 8
            reasons.append(f"requires {req}+ years (> your {criteria.max_years_required})")

    # 11. Company learnings (P2-D): confidence-gated nudges from past outcomes.
    for learning in learnings or []:
        if (learning.get("confidence") or 0) < 0.6:
            continue
        pt, obs = learning.get("pattern_type"), learning.get("observation", "")
        if pt == "offer_rate":
            # the one positive scoring nudge: this company has made offers to people like me.
            score += 4
            reasons.append(f"learning: {obs}")
        else:
            # rejection_rate / referral_conversion / process_speed are informational context,
            # not score penalties — a past rejection (often role-specific) shouldn't down-rank
            # a *different* future role, and "rejection in 0/N" must never penalize at all.
            reasons.append(f"learning: {obs}")

    score = max(0.0, min(100.0, score))
    if disq:
        score = min(score, 12.0)
    return ScoreResult(round(score, 1), reasons, knockouts, disq)
