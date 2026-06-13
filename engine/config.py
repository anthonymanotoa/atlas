"""Load and validate Atlas configuration.

`criteria.md` is a hybrid file: a YAML frontmatter block (machine-readable, used by
the deterministic scorer) followed by Markdown prose (read by the Cowork LLM brain
for nuance). Companies / sources / ontology are plain YAML.
"""
from __future__ import annotations

from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from engine.paths import (
    COMPANIES_PATH, CRITERIA_PATH, MASTER_CV_PATH, ONTOLOGY_PATH, SOURCES_PATH,
    example_fallback,
)


def load_master_cv() -> dict:
    """Load the private master_cv.yaml, falling back to the committed example."""
    path = example_fallback(MASTER_CV_PATH)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


# ── criteria ────────────────────────────────────────────────────────────────
class Criteria(BaseModel):
    roles: list[str] = Field(default_factory=list)            # core title keywords
    role_aliases: list[str] = Field(default_factory=list)     # alt titles that still count
    seniority: list[str] = Field(default_factory=lambda: ["senior", "lead", "staff", "principal"])
    remote_required: bool = True
    locations_allowed: list[str] = Field(default_factory=lambda: ["worldwide"])
    languages: list[str] = Field(default_factory=lambda: ["en", "es"])
    salary_floor_usd: float = 0.0
    salary_hard: bool = False                                  # soft by default
    must_haves: list[str] = Field(default_factory=list)
    deal_breakers: list[str] = Field(default_factory=list)
    knockout_terms: list[str] = Field(default_factory=list)
    shortlist_threshold: float = 60.0
    prose: str = ""                                            # the Markdown body (for the LLM)

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
    path = example_fallback(CRITERIA_PATH)
    if not path.exists():
        return Criteria()
    meta, prose = _split_frontmatter(path.read_text())
    meta["prose"] = prose
    return Criteria(**meta)


# ── companies (ATS registry) ─────────────────────────────────────────────────
class CompanyTarget(BaseModel):
    company: str
    ats: str                                  # greenhouse | lever | ashby | smartrecruiters
    token: Optional[str] = None               # board token / site slug / job_board_name / companyIdentifier
    instance: Optional[str] = None            # workday tenant (unused in v1)
    eu: bool = False                          # lever EU host
    careers_url: Optional[str] = None         # for re-resolution


def load_companies() -> list[CompanyTarget]:
    path = example_fallback(COMPANIES_PATH)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return [CompanyTarget(**c) for c in data.get("companies", [])]


# ── sources ──────────────────────────────────────────────────────────────────
def load_sources() -> dict[str, Any]:
    path = example_fallback(SOURCES_PATH)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


# ── ontology (skills gazetteer) ──────────────────────────────────────────────
def load_ontology() -> dict[str, list[str]]:
    """canonical skill -> [aliases/acronyms]. Used by keyword extraction + tailoring."""
    path = example_fallback(ONTOLOGY_PATH)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    out: dict[str, list[str]] = {}
    for canonical, aliases in (data.get("skills") or {}).items():
        out[canonical] = [a for a in (aliases or [])]
    return out
