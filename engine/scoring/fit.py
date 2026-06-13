"""Deterministic, explainable fit scoring (0–100) against the user's criteria.

Philosophy (from the research): the real ATS filters are knockout questions + human
triage, not a magic keyword score. So this scorer is a transparent pre-filter that
surfaces *reasons* and *knockout flags* — the Cowork brain does the nuanced ranking
of borderline matches. Deal-breakers cap the score; knockouts are flagged, not auto-rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.config import Criteria

SENIOR_TERMS = ("senior", "sr.", "sr ", "lead", "staff", "principal", "head of", "director")
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

# Minimal "obviously not EN/ES" detector (Adzuna DE/FR can return local-language posts).
_DE = (" und ", " für ", " mitarbeiter", " wir ", " sie ", " bei uns", " kenntnisse")
_FR = (" et de ", " pour ", " vous ", " nous ", " entreprise ", " compétences")


@dataclass
class ScoreResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    knockouts: list[str] = field(default_factory=list)
    disqualified: bool = False


def _has(hay: str, term: str) -> bool:
    return term.lower() in hay


def _detect_offlang(text: str, allowed: list[str]) -> str | None:
    t = f" {text.lower()} "
    if "de" not in allowed and sum(m in t for m in _DE) >= 3:
        return "de"
    if "fr" not in allowed and sum(m in t for m in _FR) >= 3:
        return "fr"
    return None


def score_job(job: dict, criteria: Criteria) -> ScoreResult:
    title = job.get("title") or ""
    title_l = title.lower()
    desc = job.get("description") or ""
    hay = f"{title_l} {desc.lower()}"

    score = 50.0
    reasons: list[str] = []
    knockouts: list[str] = []
    disq = False

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

    # 3. Seniority.
    if any(_has(title_l, t) for t in JUNIOR_TERMS):
        disq = True
        reasons.append("junior/intern level")
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

    # 8. Off-target language.
    if desc:
        off = _detect_offlang(desc, criteria.languages)
        if off:
            score -= 25
            reasons.append(f"likely {off}-language posting")

    score = max(0.0, min(100.0, score))
    if disq:
        score = min(score, 12.0)
    return ScoreResult(round(score, 1), reasons, knockouts, disq)
