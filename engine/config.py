"""Load and validate Atlas configuration.

`criteria.md` is a hybrid file: a YAML frontmatter block (machine-readable, used by
the deterministic scorer) followed by Markdown prose (read by the Cowork LLM brain
for nuance). Companies / sources / ontology are plain YAML.
"""

from __future__ import annotations

from pathlib import Path
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
    onsite_locations: list[str] = Field(default_factory=list)  # when set, a CONFIRMED on-site
    # posting whose location matches none of these is disqualified; REMOTE postings are exempt
    # (remote is worldwide). Lets a seeker say "on-site only in Ecuador, but remote from anywhere".
    # ── Geo-scoring (F2): where the candidate lives, for the remote-restriction gate ──
    candidate_country: str = ""  # ISO-2 code (e.g. "ec"); empty = geo factor OFF.
    acceptable_regions: list[str] = Field(default_factory=lambda: ["worldwide"])
    # regions (latam/eu/na/apac/emea) whose geo-restricted remote jobs still work for you. A
    # confirmed restriction outside your country/regions DISQUALIFIES the job (see fit.py 2c).
    re_apply_window_days: int = 0  # flag jobs at companies you applied to <N days ago; 0 = off
    languages: list[str] = Field(default_factory=lambda: ["en", "es"])
    language_hard: bool = False  # if True, a confidently-detected off-language posting is
    # disqualified (not just down-ranked) — for a single-language seeker (e.g. Spanish-only)
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
        ]
    )
    junior_terms: list[str] = Field(
        default_factory=lambda: [
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
    # ── Follow-up cadence v2 (F3 §6.1) — días por estado + tope de toques ──
    # applied: primer follow-up a +7d, máx 2 toques → luego COLD; responded: nudge a +1d;
    # interview: thank-you a +1d. Editable por perfil desde criteria.md.
    followup_cadence: dict[str, dict[str, int]] = Field(
        default_factory=lambda: {
            "applied": {"days": 7, "max_touches": 2},
            "responded": {"days": 1, "max_touches": 1},
            "interview": {"days": 1, "max_touches": 1},
        }
    )
    prose: str = ""  # the Markdown body (for the LLM)

    @property
    def all_role_terms(self) -> list[str]:
        return [t.lower() for t in (self.roles + self.role_aliases)]


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a `---` fenced YAML frontmatter from the trailing Markdown prose.

    Only a line that is *exactly* `---` (after stripping) counts as a fence. This avoids
    truncating the YAML when a `---` appears mid-line inside it — e.g. in a comment like
    `# --- section ---` or a quoted multiline string — which would otherwise silently drop
    every field after it back to its model default.
    """
    lines = text.splitlines()
    # The opening fence must be the first non-blank line.
    start = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if start is None or lines[start].strip() != "---":
        return {}, text.strip()
    # Find the closing fence: the next bare `---` line after the opener.
    for end in range(start + 1, len(lines)):
        if lines[end].strip() == "---":
            yaml_block = "\n".join(lines[start + 1 : end])
            prose = "\n".join(lines[end + 1 :]).strip()
            meta = yaml.safe_load(yaml_block) or {}
            return meta, prose
    return {}, text.strip()


def load_criteria() -> Criteria:
    path = example_fallback(paths.CRITERIA_PATH)
    if not path.exists():
        return Criteria()
    meta, prose = _split_frontmatter(path.read_text())
    meta["prose"] = prose
    return Criteria(**meta)


def criteria_to_markdown(criteria: Criteria) -> str:
    """Serialize a Criteria back to the hybrid criteria.md format (frontmatter + prose).

    The YAML block is emitted so `_split_frontmatter` + `Criteria(**meta)` reads it back to
    an equivalent model, and the prose is the Markdown body (never a frontmatter key).
    """
    meta = criteria.model_dump(exclude={"prose"})
    yaml_block = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    prose = criteria.prose.strip()
    return f"---\n{yaml_block}---\n" + (f"\n{prose}\n" if prose else "")


def save_criteria(criteria: Criteria) -> Path:
    """Write the ACTIVE profile's criteria.md (late path read — follows profile switches).

    Always writes paths.CRITERIA_PATH itself, never the committed `.example` fallback:
    the profile's config dir is gitignored, so personal criteria never reach the repo.
    """
    path = paths.CRITERIA_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(criteria_to_markdown(criteria))
    return path


CRITERIA_WRITABLE_FIELDS = frozenset(
    {"shortlist_threshold", "company_blocklist", "followup_cadence"}
)


def update_criteria_fields(updates: dict[str, Any]) -> Criteria:
    """Patch de campos del frontmatter YAML de criteria.md, preservando la prosa.

    Valida el resultado con el modelo Criteria ANTES de escribir (si no valida, el archivo
    no se toca). Escribe SIEMPRE en paths.CRITERIA_PATH (perfil activo, gitignorado);
    si solo existe el .example commiteado, la copia parcheada nace en la ruta real —
    el example jamás se modifica.
    """
    unknown = set(updates) - CRITERIA_WRITABLE_FIELDS
    if unknown:
        raise ValueError(f"non-writable criteria fields: {sorted(unknown)}")
    src = example_fallback(paths.CRITERIA_PATH)
    text = src.read_text() if src.exists() else ""
    meta, prose = _split_frontmatter(text)
    meta.update(updates)
    merged = Criteria(**{**meta, "prose": prose})  # valida antes de escribir
    yaml_block = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    paths.CRITERIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.CRITERIA_PATH.write_text(f"---\n{yaml_block}\n---\n\n{prose}\n")
    return merged


def default_language() -> str:
    """The profile's primary output language for generated CVs / messages — the first entry of
    criteria.languages (e.g. 'es' for a Spanish-only profile), defaulting to 'en'. Used so a
    profile generates in its own language without the caller passing --language every time."""
    langs = load_criteria().languages
    return langs[0] if langs else "en"


# ── companies (ATS registry) ─────────────────────────────────────────────────
class CompanyTarget(BaseModel):
    company: str
    ats: str  # greenhouse | lever | ashby | smartrecruiters
    token: str | None = None  # board token / site slug / job_board_name / companyIdentifier
    instance: str | None = None  # workday tenant (e.g. "nvidia" in nvidia.wd5.myworkdayjobs.com)
    eu: bool = False  # lever EU host
    careers_url: str | None = None  # for re-resolution
    demo: bool = False  # pipeline-validation board (e.g. Lever demo, Ashby) — never a real target;
    # excluded from discover() unless the profile's sources.yaml sets include_demo: true


def load_companies() -> list[CompanyTarget]:
    path = example_fallback(paths.COMPANIES_PATH)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return [CompanyTarget(**c) for c in data.get("companies", [])]


def save_company(entry: dict) -> bool:
    """Append a companies.yaml del perfil activo. False si ya existe (mismo nombre, o mismo
    ats+token). Valida con CompanyTarget antes de escribir; nunca toca el .example."""
    target = CompanyTarget(**entry)
    src = example_fallback(paths.COMPANIES_PATH)
    data = (yaml.safe_load(src.read_text()) if src.exists() else {}) or {}
    rows: list[dict] = data.get("companies") or []
    name = target.company.strip().lower()
    for c in rows:
        if (c.get("company") or "").strip().lower() == name:
            return False
        if c.get("ats") == target.ats and (c.get("token") or "") == (target.token or ""):
            return False
    dumped = {k: v for k, v in target.model_dump().items() if v not in (None, "", False)}
    rows.append(dumped)
    data["companies"] = rows
    paths.COMPANIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.COMPANIES_PATH.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return True


def load_discovery_seeds() -> list[str]:
    """Empresas candidatas para el reverse ATS discovery (F3 §6.5), del perfil activo."""
    path = example_fallback(paths.CONFIG_DIR / "discovery_seeds.yaml")
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return [str(n).strip() for n in (data.get("candidates") or []) if str(n).strip()]


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
    # An explicitly-empty proof_source means "no proof section" — never coerce it to the github
    # default (which would fire a surprise live api.github.com fetch).
    if not str(layout.get("proof_source") or "").strip():
        layout["proof_source"] = "none"
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
