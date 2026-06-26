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

# Title-ladder vocabulary (senior / exec / junior / stretch) lives on the per-profile Criteria
# model (engine/config.py) so non-data domains can redefine it — e.g. in architecture
# "Principal Architect" is a normal level (not an over-qualified stretch) and "Director of
# Design" is a valid target. score_job reads criteria.{junior,exec,senior,stretch}_terms.


def _build_stretch_re(stretch_terms: list[str]) -> re.Pattern[str] | None:
    """Word-boundary regex matching any of the profile's 'stretch' seniority titles.

    Returns None when the profile lists no stretch terms (e.g. architecture), so the stretch
    penalty is skipped entirely rather than firing on a normal senior title."""
    terms = [t.strip() for t in stretch_terms if t.strip()]
    if not terms:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.I)


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
    # Soft cap: a "stretch" posting (Staff/Principal title, or a years requirement far above
    # yours) stays visible and browsable but is held just below the shortlist threshold, so it
    # never lands in "Preseleccionados" as if it were a realistic match. Distinct from `disq`
    # (which hard-caps at 12 for true deal-breakers).
    soft_cap = 100.0
    stretch_cap = min(58.0, float(criteria.shortlist_threshold) - 4.0)

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

    # 2b. On-site location gate — when criteria.onsite_locations is set, a CONFIRMED on-site
    #     posting must be in one of them; REMOTE postings are exempt (remote is worldwide). An
    #     undetermined posting (remote unknown, or no location) is not filtered (too little signal).
    is_remote_job = is_remote == 1 or is_remote is True or wt == "remote"
    onsite_confirmed = (is_remote in (0, False)) or (wt in ("onsite", "hybrid"))
    if criteria.onsite_locations and onsite_confirmed and not is_remote_job:
        loc = (job.get("location") or "").lower()
        if loc and not any(a.lower() in loc for a in criteria.onsite_locations):
            disq = True
            knockouts.append("presencial fuera de tus ubicaciones")
            reasons.append(f"on-site outside your locations ({job.get('location')})")

    # 3. Seniority fit — junior is under-qualified (DQ); exec is over-qualified (DQ when
    #    excluded); Staff/Principal is a "stretch" (over-qualified seniority) for a candidate
    #    with fewer than criteria.stretch_min_years of experience — flagged + down-ranked.
    title_pad = f" {title_l} "
    cy = criteria.candidate_years
    stretch_re = _build_stretch_re(criteria.stretch_terms)
    # Only treat a junior title as under-qualified when the candidate isn't TARGETING junior roles.
    # A domain that lists e.g. "junior architect" as a target role wants those postings, so the
    # junior DQ must not fire on them (while a senior data candidate still rejects "Junior …").
    targets_junior = any(jt in rt for rt in role_terms for jt in criteria.junior_terms)
    if not targets_junior and any(_has(title_l, t) for t in criteria.junior_terms):
        disq = True
        reasons.append("junior/intern level (under-qualified)")
    elif criteria.exclude_exec and any(_has(title_pad, t) for t in criteria.exec_terms):
        disq = True
        knockouts.append("over-qualified (exec/management role)")
        reasons.append("exec/management title — over-qualified for an IC track")
    elif stretch_re and (stretch_m := stretch_re.search(title)):
        term = stretch_m.group(0).lower()  # the actual matched stretch title (not a fixed label)
        if cy and cy < criteria.stretch_min_years:
            score -= 12
            soft_cap = min(soft_cap, stretch_cap)  # keep it out of the shortlist
            knockouts.append(f"rol {term} (suele pedir +{criteria.stretch_min_years} años)")
            reasons.append(
                f"{term} title — typically wants ~{criteria.stretch_min_years}+ yrs (you have ~{cy})"
            )
        else:
            score += 6
            reasons.append(f"{term} seniority")
    elif any(_has(title_l, t.strip()) for t in [s.strip() for s in criteria.seniority]) or any(
        _has(title_l, t) for t in criteria.senior_terms
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

    # 8. Off-target language — use the language stored at discovery, else detect now. Soft
    #    down-rank by default; a hard single-language seeker (criteria.language_hard) disqualifies
    #    a confidently-detected off-language posting outright. Undetected postings (lang is None)
    #    are never filtered — too little signal (e.g. a description-less LinkedIn listing).
    lang = job.get("language") or detect_language(desc or title)
    if lang and lang not in criteria.languages:
        score -= 25
        reasons.append(f"likely {lang}-language posting (off-target)")
        if criteria.language_hard:
            disq = True
            knockouts.append(f"posting en otro idioma ({lang})")

    # 9. Freshness — relatively-new postings only; stale ones downranked (DQ if hard).
    if criteria.max_age_days:
        age = _age_days(job)
        if age is not None and age > criteria.max_age_days:
            score -= 15
            reasons.append(f"posted ~{age:.0f}d ago (stale, >{criteria.max_age_days}d)")
            if criteria.freshness_hard:
                disq = True

    # 10. Experience-years demand vs the candidate's real years (the realism filter). When
    #     candidate_years is set, the gap between what the posting asks and what you have
    #     drives the penalty: small gaps are fine, big ones flag + down-rank hard (so a
    #     "12+ yrs" req never out-ranks a role you can actually land). Falls back to the
    #     absolute max_years_required threshold when candidate_years is not configured.
    req = _required_years(desc) if desc else None
    if req:
        if cy:
            gap = req - cy
            if gap >= 6:
                score -= 18
                soft_cap = min(soft_cap, stretch_cap)  # a +6yr gap is a long shot — don't shortlist
                knockouts.append(f"pide {req}+ años (tienes ~{cy})")
                reasons.append(f"requires {req}+ yrs — far above your ~{cy}")
            elif gap >= 3:
                score -= 9
                knockouts.append(f"pide {req}+ años (tienes ~{cy})")
                reasons.append(f"requires {req}+ yrs (above your ~{cy})")
        elif criteria.max_years_required and req > criteria.max_years_required:
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

    score = max(0.0, min(100.0, score, soft_cap))
    if disq:
        score = min(score, 12.0)
    return ScoreResult(round(score, 1), reasons, knockouts, disq)
