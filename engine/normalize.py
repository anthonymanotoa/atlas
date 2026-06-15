"""Normalized job posting + the stable natural key used for cross-source dedupe."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from engine.lang import detect_language

# Pipeline state machine. Order matters for analytics (index = stage rank).
STATES = [
    "discovered",
    "scored",
    "shortlisted",
    "tailored",
    "drafted",
    "ready",
    "applied",
    "responded",
    "interview",
    "offer",
    "rejected",
    "closed",
    "dismissed",  # user said "not interested" — hidden from the board, restorable. No timestamp
    # column (set_state handles col-less states); never reached automatically by the pipeline.
]
STATE_RANK = {s: i for i, s in enumerate(STATES)}

# Per-stage timestamp columns kept on the jobs row (for time-in-stage analytics).
STAGE_TIMESTAMP_COLS = {
    "scored": "scored_at",
    "shortlisted": "shortlisted_at",
    "tailored": "tailored_at",
    "drafted": "drafted_at",
    "ready": "ready_at",
    "applied": "applied_at",
    "responded": "responded_at",
    "interview": "interview_at",
    "offer": "offer_at",
    "rejected": "rejected_at",
    "closed": "closed_at",
}

_WS = re.compile(r"\s+")
_NONALNUM = re.compile(r"[^a-z0-9 ]+")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def norm_text(s: str | None) -> str:
    """Lowercase, strip punctuation/extra whitespace — for dedupe keys only."""
    if not s:
        return ""
    s = s.lower().strip()
    s = _NONALNUM.sub(" ", s)
    return _WS.sub(" ", s).strip()


def norm_company(s: str | None) -> str:
    """Normalize a company name, dropping common suffixes that vary by source."""
    base = norm_text(s)
    for suffix in (
        " inc",
        " llc",
        " ltd",
        " limited",
        " gmbh",
        " corp",
        " corporation",
        " co",
        " company",
        " sa",
        " srl",
        " bv",
    ):
        if base.endswith(suffix):
            base = base[: -len(suffix)].strip()
    return base


def compute_job_id(company: str, title: str, location: str) -> str:
    """Stable cross-source natural key. Same role on Indeed + Greenhouse → one row."""
    key = f"{norm_company(company)}|{norm_text(title)}|{norm_text(location)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


_REMOTE_HINT = re.compile(r"\b(remote|remoto|work from home|wfh|anywhere|distributed)\b", re.I)
_ONSITE_HINT = re.compile(r"\b(on[- ]?site|in[- ]?office|presencial|hybrid|h[ií]brido)\b", re.I)


def infer_remote(
    location: str | None, workplace_type: str | None, text: str | None = None
) -> tuple[bool | None, str]:
    """Best-effort (is_remote, workplace_type) inference from messy source fields."""
    wt = (workplace_type or "").lower()
    if wt in ("remote", "fully remote"):
        return True, "remote"
    if wt in ("on_site", "onsite", "on-site"):
        return False, "onsite"
    if wt == "hybrid":
        return False, "hybrid"
    hay = " ".join(filter(None, [location, text]))
    if _REMOTE_HINT.search(hay) and not _ONSITE_HINT.search(hay):
        return True, "remote"
    if _ONSITE_HINT.search(hay):
        return False, "hybrid" if re.search(r"hybrid|h[ií]brido", hay, re.I) else "onsite"
    return None, "unknown"


class Job(BaseModel):
    """Normalized job posting written to the `jobs` table."""

    id: str = ""
    source: str
    source_job_id: str | None = None
    title: str
    company: str
    location: str | None = None
    is_remote: bool | None = None
    workplace_type: str = "unknown"
    url: str | None = None
    apply_url: str | None = None
    description: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None  # yearly | monthly | hourly
    date_posted: str | None = None
    language: str | None = None  # detected posting language (en|es|de|fr|pt|None)
    raw: dict[str, Any] = Field(default_factory=dict)

    def finalize(self) -> Job:
        """Fill derived fields (id, remote inference, language). Call before persisting."""
        if not self.id:
            self.id = compute_job_id(self.company, self.title, self.location or "")
        if self.is_remote is None:
            self.is_remote, self.workplace_type = infer_remote(
                self.location, self.workplace_type, self.description
            )
        if self.language is None:
            self.language = detect_language(self.description or self.title)
        return self
