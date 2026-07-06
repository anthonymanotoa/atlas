"""Normalized job posting + the stable natural key used for cross-source dedupe."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from engine.geo import COUNTRY_TO_REGION, GEO_ALIASES
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
    "expired",  # liveness gate: the posting 404s / is filled — out of the board, restorable via
    # the "expirados" filter. Col-less like `dismissed`; set only by engine/discovery/liveness.py.
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


# ── Geo-restriction extraction (F2 geo-scoring) ───────────────────────────────
# Aliases sorted longest-first so "latin america" wins over "america", "united states"
# over "us", etc. Lookarounds instead of \b so dotted aliases ("u.s.") match cleanly.
_GEO_ALT = "|".join(sorted((re.escape(a) for a in GEO_ALIASES), key=len, reverse=True))
# Location fields are short, curated strings → a bare alias scan is safe there.
_LOC_ALIAS_RE = re.compile(rf"(?<![A-Za-z])(?P<geo>{_GEO_ALT})(?![A-Za-z])", re.I)
# Bare ISO-2 codes match UPPERCASE-only and only in the location field ("Remote - US",
# "Quito, EC") — lowercased they'd collide with words ("in", "us", "it", "no").
_LOC_CODE_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(c.upper() for c in COUNTRY_TO_REGION) + r")(?![A-Za-z])"
)
# Description bodies are long free text → only anchored phrases count, and the captured
# geo must be a known alias (free text can never produce a scope).
_DESC_PATTERNS = [
    # "open to <geo>[ only]" / "hiring [in] <geo>[ only]" — a candidate-facing anchor MUST
    # precede the geo. A bare "<geo> only" suffix is deliberately NOT matched: it fires on
    # market/shipping/customer prose ("we ship to France only") that carries no residency
    # requirement, so a false country scope there would unfairly penalize a worldwide job.
    re.compile(
        rf"\b(?:open\s+to|hiring)\s+(?:in\s+)?(?:the\s+)?"
        rf"(?P<geo>{_GEO_ALT})(?:[- ]?(?:candidates|residents))?(?:\s+only)?(?![A-Za-z])",
        re.I,
    ),
    re.compile(
        rf"\bmust\s+(?:reside|be\s+based|be\s+located|live)\s+in\s+(?:the\s+)?"
        rf"(?P<geo>{_GEO_ALT})(?![A-Za-z])",
        re.I,
    ),
    re.compile(
        rf"\b(?:eligible|authori[sz]ed)\s+to\s+work\s+in\s+(?:the\s+)?"
        rf"(?P<geo>{_GEO_ALT})(?![A-Za-z])",
        re.I,
    ),
    re.compile(rf"\bwithin\s+the\s+(?P<geo>{_GEO_ALT})(?![A-Za-z])", re.I),
    re.compile(rf"\bremote\s*[(\-–—,:]\s*(?:the\s+)?(?P<geo>{_GEO_ALT})(?![A-Za-z])", re.I),
    # "only open to <geo>" / "only hiring [in] <geo>" — the mirror phrasing, "only" first.
    re.compile(
        rf"\bonly\s+(?:open\s+to|hiring)\s+(?:in\s+)?(?:the\s+)?"
        rf"(?P<geo>{_GEO_ALT})(?![A-Za-z])",
        re.I,
    ),
]
_WORLDWIDE_DESC_RE = re.compile(
    r"\b(work\s+from\s+anywhere|remote\s+worldwide|fully\s+remote,?\s+worldwide)\b", re.I
)


def extract_geo_restriction(
    location: str | None, description: str | None, is_remote: bool | int | None
) -> tuple[str | None, str]:
    """Detect a geographic restriction on a REMOTE posting.

    Returns ``(raw_text_for_ui, normalized_scope)``. Scope vocabulary (engine/geo.py):
    ISO-2 / region tokens (comma-joined when several), "worldwide", "unknown" (remote,
    nothing detected) or "" (confirmed on-site — not applicable). Deterministic regexes
    only; a match must name a known alias, so free text never yields a bogus scope.
    """
    if is_remote in (0, False):
        return None, ""
    loc = (location or "").strip()
    if loc:
        scopes: list[str] = []
        for m in _LOC_ALIAS_RE.finditer(loc):
            s = GEO_ALIASES[m.group("geo").lower()]
            if s not in scopes:
                scopes.append(s)
        for m in _LOC_CODE_RE.finditer(loc):
            s = m.group(1).lower()
            if s not in scopes:
                scopes.append(s)
        if "worldwide" in scopes:
            return loc, "worldwide"
        if scopes:
            return loc, ",".join(scopes)
    desc = description or ""
    for rx in _DESC_PATTERNS:
        m = rx.search(desc)
        if m:
            return m.group(0).strip(), GEO_ALIASES[m.group("geo").lower()]
    if _WORLDWIDE_DESC_RE.search(desc):
        return None, "worldwide"
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
    geo_restriction: str | None = None  # raw restriction text detected (shown in the UI)
    geo_scope: str = ""  # normalized: iso2/region tokens | "worldwide" | "unknown" | "" (on-site)
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
        if not self.geo_scope:
            self.geo_restriction, self.geo_scope = extract_geo_restriction(
                self.location, self.description, self.is_remote
            )
        return self
