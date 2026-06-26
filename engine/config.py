"""Load and validate Atlas configuration.

`criteria.md` is a hybrid file: a YAML frontmatter block (machine-readable, used by
the deterministic scorer) followed by Markdown prose (read by the Cowork LLM brain
for nuance). Companies / sources / ontology are plain YAML.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, Field

import engine.paths as paths
from engine.paths import example_fallback


def load_master_cv() -> dict:
    """Load the private master_cv.yaml, falling back to the committed example."""
    path = example_fallback(paths.MASTER_CV_PATH)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


# ── criteria ────────────────────────────────────────────────────────────────
class Criteria(BaseModel):
    roles: list[str] = Field(default_factory=list)  # core title keywords
    role_aliases: list[str] = Field(default_factory=list)  # alt titles that still count
    seniority: list[str] = Field(default_factory=lambda: ["senior", "lead", "staff", "principal"])
    remote_required: bool = True
    locations_allowed: list[str] = Field(default_factory=lambda: ["worldwide"])
    languages: list[str] = Field(default_factory=lambda: ["en", "es"])
    salary_floor_usd: float = 0.0
    salary_hard: bool = False  # soft by default
    must_haves: list[str] = Field(default_factory=list)
    deal_breakers: list[str] = Field(default_factory=list)
    knockout_terms: list[str] = Field(default_factory=list)
    shortlist_threshold: float = 60.0
    # ── quality gates (P1-A): keep me from chasing roles I'd never get / stale posts ──
    max_age_days: int = 0  # 0 = off; older postings are downranked (see freshness_hard)
    freshness_hard: bool = False  # if True, a stale posting is disqualified, not just downranked
    company_blocklist: list[str] = Field(default_factory=list)  # never surface these companies
    exclude_exec: bool = True  # drop director/VP/head/chief roles (over-qualified for an IC track)
    max_years_required: int = 0  # 0 = off; flag postings demanding more than N years
    # ── Seniority-fit realism (P4) — keep me off roles I realistically can't land ──
    candidate_years: int = 0  # your real years of experience; 0 = off. Powers realistic
    # years-gap scoring (a "12+ yrs" posting is flagged + down-ranked when you have ~5) and
    # demotes Staff/Principal titles (which usually want 8+ yrs) instead of bonusing them.
    # ── Title-ladder vocabulary (per-domain; defaults preserve the data/IC-track behavior) ──
    # These were hardcoded constants in engine/scoring/fit.py; promoting them to the profile
    # lets non-data domains redefine seniority (e.g. architecture: "Principal Architect" is a
    # normal level, not an over-qualified stretch; "Director of Design" is a valid target).
    senior_terms: list[str] = Field(default_factory=lambda: ["senior", "sr.", "sr ", "lead"])
    exec_terms: list[str] = Field(
        default_factory=lambda: [
            "director", "vp ", "vp,", "vice president", "head of", "chief", " cto", " ceo",
            " cfo", " coo", "svp", "evp", "c-level", "managing director",
        ]
    )
    junior_terms: list[str] = Field(
        default_factory=lambda: [
            "junior", "jr.", "jr ", "intern", "internship", "entry level", "entry-level",
            "graduate", "trainee", "becario", "practicante", "working student", "apprentice",
        ]
    )
    stretch_terms: list[str] = Field(
        default_factory=lambda: ["staff", "principal", "distinguished", "fellow"]
    )  # titles that usually want many years; penalized below stretch_min_years. Empty = no penalty.
    stretch_min_years: int = 8  # below this many years, a stretch-title posting is down-ranked
    # ── Positioning / advisor (per-domain; empty defaults are domain-neutral) ──
    repositioning_target: str = ""  # e.g. "AI/ML"; empty = advisor won't push any re-framing
    core_keywords: list[str] = Field(default_factory=list)  # must-appear terms the CV audit checks
    # ── CV tailoring tuning (promoted from engine/cv constants; defaults unchanged) ──
    top_jd_keywords: int = 25  # how many JD keywords to extract/rank
    max_skills: int = 18  # cap on rendered skills
    max_highlights_per_role: int = 4  # cap on highlights per experience entry
    prose: str = ""  # the Markdown body (for the LLM)

    @property
    def all_role_terms(self) -> list[str]:
        return [t.lower() for t in (self.roles + self.role_aliases)]


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if text.lstrip().startswith("---"):
        body = text.lstrip()
        parts = body.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            return meta, parts[2].strip()
    return {}, text.strip()


def load_criteria() -> Criteria:
    path = example_fallback(paths.CRITERIA_PATH)
    if not path.exists():
        return Criteria()
    meta, prose = _split_frontmatter(path.read_text())
    meta["prose"] = prose
    return Criteria(**meta)


# ── companies (ATS registry) ─────────────────────────────────────────────────
class CompanyTarget(BaseModel):
    company: str
    ats: str  # greenhouse | lever | ashby | smartrecruiters
    token: str | None = None  # board token / site slug / job_board_name / companyIdentifier
    instance: str | None = None  # workday tenant (e.g. "nvidia" in nvidia.wd5.myworkdayjobs.com)
    eu: bool = False  # lever EU host
    careers_url: str | None = None  # for re-resolution


def load_companies() -> list[CompanyTarget]:
    path = example_fallback(paths.COMPANIES_PATH)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return [CompanyTarget(**c) for c in data.get("companies", [])]


# ── sources ──────────────────────────────────────────────────────────────────
def load_sources() -> dict[str, Any]:
    path = example_fallback(paths.SOURCES_PATH)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


# ── CV layout (per-domain section order / labels / portfolio proof-source) ────
_DEFAULT_CV_LAYOUT: dict = {
    # The legacy data layout — used when a profile ships no cv_layout.yaml.
    "order": ["summary", "skills", "experience", "education", "certs", "projects"],
    "labels": {},  # {section_key: {en: "...", es: "..."}} heading overrides
    "proof_source": "github",  # github | visual_gallery | none — used by the portfolio builder
}


def load_cv_layout() -> dict:
    """Per-profile CV section order, heading overrides, and portfolio proof-source.

    Falls back to the legacy data layout when no cv_layout.yaml is present, so existing
    profiles render exactly as before."""
    path = example_fallback(paths.CV_LAYOUT_PATH)
    if not path.exists():
        return dict(_DEFAULT_CV_LAYOUT)
    data = yaml.safe_load(path.read_text()) or {}
    layout = dict(_DEFAULT_CV_LAYOUT)
    layout.update({k: v for k, v in data.items() if v is not None})
    return layout


# ── interview question banks (per-domain) ────────────────────────────────────
def load_interview_topics() -> dict:
    """Per-profile interview banks: {behavioral, role_topics, default_tech}.

    Empty dict when no interview_topics.yaml is present — interview_prep then falls back to its
    embedded data banks, so existing profiles are unchanged."""
    path = example_fallback(paths.INTERVIEW_TOPICS_PATH)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


# ── ontology (skills gazetteer) ──────────────────────────────────────────────
def load_ontology() -> dict[str, list[str]]:
    """canonical skill -> [aliases/acronyms]. Used by keyword extraction + tailoring."""
    path = example_fallback(paths.ONTOLOGY_PATH)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    out: dict[str, list[str]] = {}
    for canonical, aliases in (data.get("skills") or {}).items():
        out[canonical] = [a for a in (aliases or [])]  # noqa: C416
    return out
