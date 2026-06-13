"""Tailor the master CV to a specific job — truthfully.

The deterministic engine NEVER invents skills or metrics. It only:
  • reorders the user's real skills to surface JD-matched ones first,
  • selects the most JD-relevant real highlights per role,
  • sets a target-title line to the exact posting title,
  • computes a transparent keyword COVERAGE report (matched vs missing), and
  • prepares dual-form acronym displays ("Machine Learning (ML)").
The Cowork LLM may then reword bullets (still truthfully) before rendering.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from engine.cv.keywords import KeywordHit, build_alias_index, extract_jd_keywords

MAX_SKILLS = 18
MAX_HIGHLIGHTS_PER_ROLE = 4
TOP_JD_KEYWORDS = 25


@dataclass
class TailorResult:
    cv: dict
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    coverage: float = 0.0
    target_title: str = ""
    ats_target: str = "unknown"
    jd_keywords: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def detect_ats(apply_url: str | None) -> str:
    u = (apply_url or "").lower()
    for needle, name in [("greenhouse", "greenhouse"), ("lever.co", "lever"),
                         ("ashbyhq", "ashby"), ("myworkdayjobs", "workday"),
                         ("taleo", "taleo"), ("smartrecruiters", "smartrecruiters"),
                         ("icims", "icims"), ("linkedin", "linkedin"), ("indeed", "indeed")]:
        if needle in u:
            return name
    return "unknown"


def _canon_of(skill: str, alias_index: dict[str, str]) -> str:
    return alias_index.get(skill.lower(), skill)


def _acronym_for(canonical: str, ontology: dict[str, list[str]]) -> str | None:
    """Return the short acronym for a multiword skill ('machine learning' -> 'ML')."""
    if " " not in canonical:
        return None
    for alias in ontology.get(canonical, []):
        if 2 <= len(alias) <= 4 and alias.isalpha():
            return alias.upper()
    return None


def _dual_form(skill: str, alias_index: dict[str, str], ontology: dict[str, list[str]]) -> str:
    """Append a dual-form acronym to the user's skill, preserving their casing.
    'Machine Learning' -> 'Machine Learning (ML)'; 'AWS Redshift' stays unchanged."""
    canon = _canon_of(skill, alias_index)
    acr = _acronym_for(canon, ontology)
    if acr and acr.lower() not in skill.lower():
        return f"{skill} ({acr})"
    return skill


def _highlight_relevance(text: str, tags: list[str], jd_canon: set[str],
                         alias_index: dict[str, str]) -> int:
    score = 0
    low = text.lower()
    for canon in jd_canon:
        if canon in low or any(canon in t for t in [low]):
            score += 1
    for t in tags or []:
        if _canon_of(t, alias_index) in jd_canon:
            score += 1
    return score


def tailor(master: dict, job: dict, ontology: dict[str, list[str]]) -> TailorResult:
    alias_index = build_alias_index(ontology)
    title = job.get("title") or ""
    desc = job.get("description") or ""
    hits: list[KeywordHit] = extract_jd_keywords(title, desc, ontology)[:TOP_JD_KEYWORDS]
    jd_canon = {h.canonical for h in hits}

    cv = copy.deepcopy(master)

    # User's real skills, canonicalized.
    user_skills = cv.get("skills", []) or []
    user_canon = {_canon_of(s, alias_index): s for s in user_skills}

    # Also treat skills mentioned in highlights/summary as "covered" for the report.
    corpus = " ".join([
        cv.get("basics", {}).get("summary", "") or "",
        *[h for exp in cv.get("experience", []) for h in (exp.get("highlights") or [])],
        *[" ".join(exp.get("skills", []) or []) for exp in cv.get("experience", [])],
    ]).lower()

    matched, missing = [], []
    for h in hits:
        if h.canonical in user_canon or h.canonical in corpus or h.surface.lower() in corpus:
            matched.append(h.canonical)
        else:
            missing.append(h.canonical)
    coverage = round(len(matched) / max(len(hits), 1), 3)

    # Reorder skills: JD-matched (in importance order) first, then the rest. Cap + dual-form.
    jd_order = [h.canonical for h in hits]
    ranked = [s for c in jd_order for s in [user_canon.get(c)] if s]
    rest = [s for s in user_skills if s not in ranked]
    ordered = (ranked + rest)[:MAX_SKILLS]
    cv["skills"] = [_dual_form(s, alias_index, ontology) for s in ordered]

    # Select most relevant real highlights per role (keep >=2, top-N).
    for exp in cv.get("experience", []):
        hl = exp.get("highlights") or []
        scored = sorted(hl, key=lambda t: _highlight_relevance(t, exp.get("skills", []),
                                                               jd_canon, alias_index), reverse=True)
        exp["highlights"] = scored[:max(MAX_HIGHLIGHTS_PER_ROLE, 2)] if len(hl) > 2 else hl

    # Target-title line (truthful objective; exact posting title is high-ROI).
    target_title = re.sub(r"\s+", " ", title).strip()
    if target_title:
        cv.setdefault("basics", {})["label"] = target_title

    ats_target = detect_ats(job.get("apply_url") or job.get("url"))
    notes = []
    if missing:
        notes.append("Missing JD keywords you may genuinely have — confirm before adding: "
                     + ", ".join(missing[:8]))
    return TailorResult(cv=cv, matched=matched, missing=missing, coverage=coverage,
                        target_title=target_title, ats_target=ats_target,
                        jd_keywords=jd_order, notes=notes)
