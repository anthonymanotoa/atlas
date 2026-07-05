# Atlas v2 — Fase 2: Onboarding + Geo-scoring + Higiene — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-profile web onboarding wizard, deterministic geo-restriction scoring for remote jobs, and pipeline hygiene (liveness gate, repost/ghost detection, geo-mismatch flags, re-apply window, posting snapshots) — spec §5 of `docs/superpowers/specs/2026-07-04-atlas-v2-design.md`.

**Architecture:** Everything stays deterministic and $0 (no LLM calls). A new `engine/geo.py` gazetteer feeds a regex extractor in `engine/normalize.py` that writes two new `jobs` columns (`geo_restriction`, `geo_scope`); `engine/scoring/fit.py` gains factor 2c (geo penalty, never DQ) + 2d (remote/on-site contradiction flag) + a repost penalty. Hygiene lives in two new modules (`engine/discovery/liveness.py`, `engine/reposts.py`) hooked into the discovery runner and exposed via origin-guarded FastAPI endpoints. The wizard is a React multi-step component backed by new `GET/PUT /api/criteria` + `POST /api/cv/import` endpoints that read/write the active profile's gitignored `criteria.md` / `master_cv.draft.yaml`.

**Tech Stack:** Python 3.11+ (FastAPI, pydantic v2, httpx, sqlite3, pdfplumber/python-docx already present; adds `python-multipart` for the upload endpoint), React 19 + TS + Tailwind v4 + shadcn-style primitives in `dashboard/frontend/src/components/ui/`, pytest + Vitest.

## Global Constraints

- **Backend tests ALWAYS run via `rtk uv run --group dev pytest ...`** — never bare `pytest`, never `--extra dev`.
- **Frontend gate:** `npm --prefix dashboard/frontend test` and `npm --prefix dashboard/frontend run build`; run `npm --prefix dashboard/frontend run format` before committing TSX (repo enforces `format:check`).
- **Every new state-mutating endpoint (POST/PUT) carries `dependencies=[Depends(require_trusted_origin)]`** (pattern already in `dashboard/backend/main.py`).
- **DB migrations:** new columns on existing tables ONLY via the guarded `self._ensure_column(...)` pattern in `engine/db/models.py::DB._migrate`; brand-new tables go in `engine/db/schema.sql` as `CREATE TABLE IF NOT EXISTS`.
- **Public repo:** personal data lives only in gitignored paths (`profiles/<id>/`, per-profile `config/`, `data/`). Tests and docs use a **fictional candidate**; `candidate_country` defaults to `""` (factor OFF) — never hardcode a real country (e.g. Ecuador) as a code default.
- **Geo scoring is conservative:** scope `"unknown"` / `""` / `"worldwide"` never penalizes; the geo factor **never disqualifies**.
- **$0 invariant:** no API keys, no LLM calls — regexes, HTTP status checks and SQL only.
- **Paths are read late:** `import engine.paths as paths` then `paths.CRITERIA_PATH` (never `from engine.paths import CRITERIA_PATH`).
- **Commits:** add ONLY the files you touched, by name (`rtk git add <file1> <file2>` — never `git add .`/`-A`); every commit message ends with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- F2 builds on F1 (router, `/onboarding` route, design system v2). Where F1 moved a component (e.g. `DetailDrawer` → a `/jobs/:id` page), locate the render site with the `rtk grep` command given in the task and apply the snippet there; the snippets use only semantic token classes and shared `ui/` primitives, so they are F1-safe.

---

## File Structure

**New files**
- `engine/geo.py` — country→region map, text aliases, `geo_scope_covers()` predicate.
- `engine/reposts.py` — repost/ghost sweep (`core_title()`, `sweep_reposts()`).
- `engine/discovery/liveness.py` — per-URL liveness check + batch sweep.
- `tests/test_geo.py`, `tests/test_geo_extraction.py`, `tests/test_db_geo.py`, `tests/test_geo_scoring.py`, `tests/test_reposts.py`, `tests/test_liveness.py`, `tests/test_liveness_api.py`, `tests/test_reapply_window.py`, `tests/test_snapshots.py`, `tests/test_criteria_save.py`, `tests/test_criteria_api.py`, `tests/test_cv_import_api.py`
- `dashboard/frontend/src/components/JobBadges.tsx` (+ `JobBadges.test.tsx`) — geo + repost chips shared by card and detail.
- `dashboard/frontend/src/components/onboarding/OnboardingWizard.tsx` (+ `OnboardingWizard.test.tsx`).

**Modified files**
- `engine/normalize.py` — `extract_geo_restriction()`, `Job.geo_restriction/geo_scope`, `finalize()`, `STATES` += `"expired"`.
- `engine/db/models.py` — 4 new guarded columns; `upsert_job` persists geo fields; `snapshot_posting()`/`snapshots_for()`.
- `engine/db/schema.sql` — geo columns on the canonical schema + `posting_snapshots` table.
- `engine/config.py` — 4 new `Criteria` fields; `criteria_to_markdown()` + `save_criteria()`.
- `engine/scoring/fit.py` — factors 2c (geo penalty), 2d (geo-mismatch flag), 7b (repost penalty).
- `engine/scoring/run.py` — re-apply-window flag.
- `engine/discovery/runner.py` — repost sweep always; liveness sweep opt-in.
- `dashboard/backend/main.py` — `GET/PUT /api/criteria`, `POST /api/cv/import`, `POST /api/liveness/sweep` + status, snapshot on applied.
- `pyproject.toml` — `python-multipart` dependency.
- `config/seeds/{default,data,architecture}/criteria.example.md` + `config/criteria.example.md` — new frontmatter keys.
- `config/seeds/{default,data,architecture}/sources.yaml` + `config/sources.yaml` — `liveness:` block.
- `dashboard/frontend/src/api.ts` — `put`/`postForm` helpers, `CriteriaConfig`, new Job fields, new api entries.
- `dashboard/frontend/src/components/Board.tsx` — badges on the kanban card.
- Job-detail component (F1's `/jobs/:id` page, or `DetailDrawer.tsx` pre-F1) — badges in the header chip row.
- The component that renders `OnboardingGate` (F1's `/onboarding` route, or `App.tsx` pre-F1) — swapped to `OnboardingWizard`; `OnboardingGate.tsx` deleted.

---

### Task 1: `engine/geo.py` — country/region gazetteer + coverage predicate

**Files:**
- Create: `engine/geo.py`
- Test: `tests/test_geo.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces:
  - `COUNTRY_TO_REGION: dict[str, str]` — ISO-2 (lowercase) → `"latam" | "eu" | "na" | "apac"` (~73 countries).
  - `GEO_ALIASES: dict[str, str]` — lowercase text alias → scope token (ISO-2, region, `"emea"`, or `"worldwide"`).
  - `region_of(country: str) -> str | None`
  - `geo_scope_covers(scope: str, country: str, regions: list[str]) -> bool`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_geo.py`:

```python
"""Geo gazetteer + the coverage predicate the scorer uses (F2 geo-scoring)."""

from __future__ import annotations

from engine.geo import COUNTRY_TO_REGION, GEO_ALIASES, geo_scope_covers, region_of


def test_map_has_the_four_regions_and_a_sane_size():
    assert set(COUNTRY_TO_REGION.values()) == {"latam", "eu", "na", "apac"}
    assert 60 <= len(COUNTRY_TO_REGION) <= 90


def test_region_of_common_countries():
    assert region_of("ec") == "latam"
    assert region_of("us") == "na"
    assert region_of("de") == "eu"
    assert region_of("sg") == "apac"
    assert region_of("zz") is None


def test_aliases_normalize_to_scope_tokens():
    assert GEO_ALIASES["united states"] == "us"
    assert GEO_ALIASES["usa"] == "us"
    assert GEO_ALIASES["uk"] == "gb"
    assert GEO_ALIASES["latin america"] == "latam"
    assert GEO_ALIASES["worldwide"] == "worldwide"


def test_covers_worldwide_unknown_and_blank():
    assert geo_scope_covers("worldwide", "ec", []) is True
    assert geo_scope_covers("unknown", "ec", []) is True
    assert geo_scope_covers("", "ec", []) is True


def test_covers_own_country_and_own_region():
    assert geo_scope_covers("ec", "ec", []) is True          # exact country
    assert geo_scope_covers("latam", "ec", []) is True       # candidate's region
    assert geo_scope_covers("us,ca", "ec", []) is False      # neither


def test_covers_acceptable_regions():
    # Region token in scope intersects acceptable_regions…
    assert geo_scope_covers("eu", "ec", ["eu"]) is True
    # …and a country token inside an acceptable region also covers ("br" ⊂ latam).
    assert geo_scope_covers("br", "ec", ["latam"]) is True
    # "worldwide" in acceptable_regions does NOT whitelist restricted scopes.
    assert geo_scope_covers("us", "ec", ["worldwide"]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_geo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.geo'`

- [ ] **Step 3: Write the implementation**

Create `engine/geo.py`:

```python
"""Country/region gazetteer + geo-scope logic for remote-restriction scoring (F2).

Deterministic and dependency-free: a small embedded map of common countries onto the four
coarse regions the scorer reasons about (latam / eu / na / apac), the text aliases the
extractor in engine/normalize.py recognizes, and the single coverage predicate the scorer
(engine/scoring/fit.py, factor 2c) calls.

Scope tokens — the ``jobs.geo_scope`` vocabulary:
  * ISO-2 country codes ("us", "gb", "ec", ...)
  * regions: "latam" | "eu" | "na" | "apac" | "emea"
  * "worldwide" (explicitly unrestricted) | "unknown" (remote, nothing detected)
  * ""          (not applicable: confirmed on-site posting)
Multiple tokens are comma-joined ("us,ca").
"""

from __future__ import annotations

# ISO-2 → coarse region. "eu" means geographic Europe: the restriction language in real
# postings ("Europe only", "EU-based") almost never distinguishes EU membership, so we don't.
COUNTRY_TO_REGION: dict[str, str] = {
    # LatAm (20)
    "ar": "latam", "bo": "latam", "br": "latam", "cl": "latam", "co": "latam",
    "cr": "latam", "cu": "latam", "do": "latam", "ec": "latam", "gt": "latam",
    "hn": "latam", "mx": "latam", "ni": "latam", "pa": "latam", "pe": "latam",
    "pr": "latam", "py": "latam", "sv": "latam", "uy": "latam", "ve": "latam",
    # North America (2)
    "ca": "na", "us": "na",
    # Europe (33)
    "at": "eu", "be": "eu", "bg": "eu", "ch": "eu", "cy": "eu", "cz": "eu",
    "de": "eu", "dk": "eu", "ee": "eu", "es": "eu", "fi": "eu", "fr": "eu",
    "gb": "eu", "gr": "eu", "hr": "eu", "hu": "eu", "ie": "eu", "is": "eu",
    "it": "eu", "lt": "eu", "lu": "eu", "lv": "eu", "mt": "eu", "nl": "eu",
    "no": "eu", "pl": "eu", "pt": "eu", "ro": "eu", "rs": "eu", "se": "eu",
    "si": "eu", "sk": "eu", "ua": "eu",
    # APAC (18)
    "au": "apac", "bd": "apac", "cn": "apac", "hk": "apac", "id": "apac",
    "in": "apac", "jp": "apac", "kr": "apac", "lk": "apac", "my": "apac",
    "np": "apac", "nz": "apac", "ph": "apac", "pk": "apac", "sg": "apac",
    "th": "apac", "tw": "apac", "vn": "apac",
}

# Text alias (lowercase) → scope token. Only UNAMBIGUOUS aliases belong here: full country
# names, region names, and safe short forms. Bare ISO-2 codes are deliberately absent —
# lowercased they collide with English/Spanish words ("in", "us", "it", "no", "es") — and
# are matched separately, uppercase-only, in the location field (see engine/normalize.py).
GEO_ALIASES: dict[str, str] = {
    # US / UK / safe short forms
    "united states": "us", "usa": "us", "u.s.": "us", "u.s.a.": "us", "us": "us",
    "america": "us",
    "united kingdom": "gb", "uk": "gb", "u.k.": "gb", "great britain": "gb",
    "england": "gb",
    # LatAm countries
    "argentina": "ar", "bolivia": "bo", "brazil": "br", "brasil": "br", "chile": "cl",
    "colombia": "co", "costa rica": "cr", "cuba": "cu", "dominican republic": "do",
    "ecuador": "ec", "el salvador": "sv", "guatemala": "gt", "honduras": "hn",
    "mexico": "mx", "méxico": "mx", "nicaragua": "ni", "panama": "pa", "panamá": "pa",
    "paraguay": "py", "peru": "pe", "perú": "pe", "puerto rico": "pr", "uruguay": "uy",
    "venezuela": "ve",
    # North America
    "canada": "ca", "canadá": "ca",
    # Europe
    "austria": "at", "belgium": "be", "bulgaria": "bg", "croatia": "hr", "cyprus": "cy",
    "czech republic": "cz", "czechia": "cz", "denmark": "dk", "estonia": "ee",
    "finland": "fi", "france": "fr", "germany": "de", "deutschland": "de", "greece": "gr",
    "hungary": "hu", "iceland": "is", "ireland": "ie", "italy": "it", "italia": "it",
    "latvia": "lv", "lithuania": "lt", "luxembourg": "lu", "malta": "mt",
    "netherlands": "nl", "the netherlands": "nl", "norway": "no", "poland": "pl",
    "portugal": "pt", "romania": "ro", "serbia": "rs", "slovakia": "sk", "slovenia": "si",
    "spain": "es", "españa": "es", "sweden": "se", "switzerland": "ch", "ukraine": "ua",
    # APAC
    "australia": "au", "bangladesh": "bd", "china": "cn", "hong kong": "hk", "india": "in",
    "indonesia": "id", "japan": "jp", "korea": "kr", "south korea": "kr", "malaysia": "my",
    "nepal": "np", "new zealand": "nz", "pakistan": "pk", "philippines": "ph",
    "singapore": "sg", "sri lanka": "lk", "taiwan": "tw", "thailand": "th", "vietnam": "vn",
    # Regions
    "latam": "latam", "latin america": "latam", "latinoamérica": "latam",
    "latinoamerica": "latam", "américa latina": "latam", "america latina": "latam",
    "south america": "latam", "central america": "latam",
    "europe": "eu", "european union": "eu", "eu": "eu", "emea": "emea",
    "north america": "na",
    "apac": "apac", "asia pacific": "apac", "asia-pacific": "apac",
    # Explicitly unrestricted
    "worldwide": "worldwide", "anywhere": "worldwide", "global": "worldwide",
    "globally": "worldwide",
}


def region_of(country: str) -> str | None:
    """The coarse region of an ISO-2 country code, or None for unknown codes."""
    return COUNTRY_TO_REGION.get((country or "").strip().lower())


def geo_scope_covers(scope: str, country: str, regions: list[str]) -> bool:
    """True when a job's geo scope admits the candidate (→ the scorer must NOT penalize).

    ``scope`` is the ``jobs.geo_scope`` value (comma-joined scope tokens); ``country`` is
    the candidate's ISO-2 code; ``regions`` is criteria.acceptable_regions. Blank/worldwide/
    unknown scopes always cover — we never penalize on missing signal. "worldwide" inside
    ``regions`` is the default no-op (it expresses "unrestricted remote is fine"), NOT a
    whitelist for restricted scopes.
    """
    parts = {p.strip().lower() for p in (scope or "").split(",") if p.strip()}
    if not parts or parts & {"worldwide", "unknown"}:
        return True
    cc = (country or "").strip().lower()
    if cc and cc in parts:
        return True
    creg = COUNTRY_TO_REGION.get(cc)
    if creg and creg in parts:
        return True
    accept = {r.strip().lower() for r in regions if r and r.strip().lower() != "worldwide"}
    if parts & accept:
        return True
    # A country token that lies inside an acceptable region ("br" ⊂ "latam").
    return any(COUNTRY_TO_REGION.get(p) in accept for p in parts if COUNTRY_TO_REGION.get(p))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_geo.py -v`
Expected: 6 passed

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/geo.py tests/test_geo.py && rtk uv run ruff format engine/geo.py tests/test_geo.py
rtk git add engine/geo.py tests/test_geo.py
rtk git commit -m "feat(geo): country/region gazetteer + geo_scope_covers predicate

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `extract_geo_restriction()` in `engine/normalize.py` + Job fields

**Files:**
- Modify: `engine/normalize.py` (imports at top; new code after `infer_remote`, ~line 113; `Job` fields after `language`, ~line 136; `finalize()` ~lines 139–149)
- Test: `tests/test_geo_extraction.py`

**Interfaces:**
- Consumes: `engine.geo.GEO_ALIASES`, `engine.geo.COUNTRY_TO_REGION` (Task 1).
- Produces:
  - `extract_geo_restriction(location: str | None, description: str | None, is_remote: bool | int | None) -> tuple[str | None, str]` — returns `(raw_text_for_ui, normalized_scope)`.
  - `Job.geo_restriction: str | None = None`, `Job.geo_scope: str = ""` — filled by `Job.finalize()`.

- [ ] **Step 1: Write the failing tests (spec §8 corpus + description patterns)**

Create `tests/test_geo_extraction.py`:

```python
"""Deterministic geo-restriction extraction for remote postings (spec §5.2 / §8 corpus)."""

from __future__ import annotations

from engine.normalize import Job, extract_geo_restriction


# ── The mandatory corpus from the spec (§8) ──────────────────────────────────
def test_remote_us_only_location():
    raw, scope = extract_geo_restriction("Remote — US only", "", True)
    assert scope == "us"
    assert raw == "Remote — US only"


def test_remote_must_be_uk_based_location():
    raw, scope = extract_geo_restriction("Remote (must be UK-based)", "", True)
    assert scope == "gb"
    assert raw == "Remote (must be UK-based)"


def test_remote_latam_location():
    assert extract_geo_restriction("Remote LatAm", "", True)[1] == "latam"


def test_remote_worldwide_location():
    assert extract_geo_restriction("Remote worldwide", "", True)[1] == "worldwide"


def test_remote_without_restriction_is_unknown():
    assert extract_geo_restriction("Remote", "Great team, async culture.", True) == (
        None,
        "unknown",
    )


def test_onsite_is_not_applicable():
    assert extract_geo_restriction("Quito, Ecuador", "on-site role", False) == (None, "")


# ── Description-body patterns ────────────────────────────────────────────────
def test_must_reside_in():
    raw, scope = extract_geo_restriction(
        "Remote", "You must reside in the United States to apply.", True
    )
    assert scope == "us"
    assert raw == "must reside in the United States"


def test_must_be_based_in():
    assert extract_geo_restriction("Remote", "Candidates must be based in Germany.", True)[1] == "de"


def test_eligible_to_work_in():
    assert extract_geo_restriction("Remote", "Must be eligible to work in Canada.", True)[1] == "ca"


def test_authorized_to_work_in():
    assert (
        extract_geo_restriction("Remote", "You are authorized to work in the UK.", True)[1] == "gb"
    )


def test_remote_paren_us():
    assert extract_geo_restriction("", "This role is Remote (US).", True)[1] == "us"


def test_remote_dash_usa_location():
    assert extract_geo_restriction("Remote - USA", "", True)[1] == "us"


def test_within_the_eu():
    assert extract_geo_restriction("Remote", "You are located within the EU.", True)[1] == "eu"


def test_country_only_suffix_in_description():
    raw, scope = extract_geo_restriction("Remote", "Open to Brazil only.", True)
    assert scope == "br"


def test_specific_country_in_remote_location():
    # A remote job whose location names a country IS a restriction signal (spec §5.2).
    assert extract_geo_restriction("Remote - Poland", "", True)[1] == "pl"


def test_uppercase_iso2_code_in_location():
    assert extract_geo_restriction("Remote - Quito, EC", "", True)[1] == "ec"


def test_lowercase_word_us_never_matches_description():
    # "join us" must never read as a US restriction — description matches are anchored.
    assert extract_geo_restriction("Remote", "Come join us on our mission!", True)[1] == "unknown"


# ── Job.finalize wiring ──────────────────────────────────────────────────────
def test_finalize_fills_geo_fields():
    j = Job(
        source="himalayas",
        title="Data Engineer",
        company="Acme",
        location="Remote — US only",
        is_remote=True,
    ).finalize()
    assert j.geo_scope == "us"
    assert j.geo_restriction == "Remote — US only"


def test_finalize_onsite_gets_empty_scope():
    j = Job(
        source="indeed",
        title="Data Engineer",
        company="Acme",
        location="Berlin, Germany",
        is_remote=False,
        workplace_type="onsite",
    ).finalize()
    assert j.geo_scope == ""
    assert j.geo_restriction is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_geo_extraction.py -v`
Expected: FAIL — `ImportError: cannot import name 'extract_geo_restriction' from 'engine.normalize'`

- [ ] **Step 3: Implement in `engine/normalize.py`**

3a. Add the import (after `from engine.lang import detect_language`, line 12):

```python
from engine.geo import COUNTRY_TO_REGION, GEO_ALIASES
```

3b. Insert after `infer_remote` (after line 113) and before `class Job`:

```python
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
    re.compile(rf"\b(?P<geo>{_GEO_ALT})[- ]?(?:candidates\s+|residents\s+)?only\b", re.I),
    re.compile(
        rf"\bmust\s+(?:reside|be\s+based|be\s+located|live)\s+in\s+(?:the\s+)?"
        rf"(?P<geo>{_GEO_ALT})(?![A-Za-z])",
        re.I,
    ),
    re.compile(rf"\bbased\s+in\s+(?:the\s+)?(?P<geo>{_GEO_ALT})(?![A-Za-z])", re.I),
    re.compile(
        rf"\b(?:eligible|authori[sz]ed)\s+to\s+work\s+in\s+(?:the\s+)?"
        rf"(?P<geo>{_GEO_ALT})(?![A-Za-z])",
        re.I,
    ),
    re.compile(rf"\bwithin\s+the\s+(?P<geo>{_GEO_ALT})(?![A-Za-z])", re.I),
    re.compile(
        rf"\bremote\s*[(\-–—,:]\s*(?:the\s+)?(?P<geo>{_GEO_ALT})(?![A-Za-z])", re.I
    ),
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
```

3c. Add the two fields to `Job` (after `language`, line 136):

```python
    geo_restriction: str | None = None  # raw restriction text detected (shown in the UI)
    geo_scope: str = ""  # normalized: iso2/region tokens | "worldwide" | "unknown" | "" (on-site)
```

3d. Extend `Job.finalize()` — insert before `if self.language is None:`:

```python
        if not self.geo_scope:
            self.geo_restriction, self.geo_scope = extract_geo_restriction(
                self.location, self.description, self.is_remote
            )
```

- [ ] **Step 4: Run tests to verify they pass (plus no regressions in normalize consumers)**

Run: `rtk uv run --group dev pytest tests/test_geo_extraction.py tests/test_engine.py tests/test_parsers.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/normalize.py tests/test_geo_extraction.py && rtk uv run ruff format engine/normalize.py tests/test_geo_extraction.py
rtk git add engine/normalize.py tests/test_geo_extraction.py
rtk git commit -m "feat(normalize): deterministic geo-restriction extraction for remote postings

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `jobs` columns (geo + hygiene) via the guarded ADD COLUMN pattern

**Files:**
- Modify: `engine/db/models.py` (`_migrate`, lines 70–72; `upsert_job` INSERT lines 99–129 and gap-fill UPDATE lines 137–167)
- Modify: `engine/db/schema.sql` (jobs table, after `language` line 22)
- Test: `tests/test_db_geo.py`

**Interfaces:**
- Consumes: `Job.geo_restriction` / `Job.geo_scope` (Task 2).
- Produces: `jobs.geo_restriction TEXT`, `jobs.geo_scope TEXT`, `jobs.repost_count INTEGER DEFAULT 0`, `jobs.liveness_checked_at TEXT` — all readable as plain dict keys from `db.list_jobs()` / `db.get_job()` (used by Tasks 5, 7, 8, 14).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db_geo.py`:

```python
"""F2 jobs columns: guarded migration + geo persistence through upsert_job."""

from __future__ import annotations

from engine.db.models import DB
from engine.normalize import Job


def test_migration_adds_f2_columns(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        cols = {r["name"] for r in db.conn.execute("PRAGMA table_info(jobs)")}
    assert {"geo_restriction", "geo_scope", "repost_count", "liveness_checked_at"} <= cols


def test_upsert_persists_geo_fields(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(
                source="himalayas",
                title="Data Engineer",
                company="Acme",
                location="Remote — US only",
                is_remote=True,
            )
        )
        row = db.list_jobs()[0]
    assert row["geo_scope"] == "us"
    assert row["geo_restriction"] == "Remote — US only"


def test_enrichment_upgrades_unknown_scope(tmp_path):
    """A richer source that reveals a restriction upgrades a previously-unknown scope."""
    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(source="linkedin", title="DE", company="Acme", location="Remote", is_remote=True)
        )
        assert db.list_jobs()[0]["geo_scope"] == "unknown"
        db.upsert_job(
            Job(
                source="greenhouse",
                title="DE",
                company="Acme",
                location="Remote",
                is_remote=True,
                description="You must reside in the United States.",
            )
        )
        row = db.list_jobs()[0]
    assert row["geo_scope"] == "us"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_db_geo.py -v`
Expected: FAIL — `assert {'geo_restriction', ...} <= cols` (columns missing) and `KeyError: 'geo_scope'`

- [ ] **Step 3: Implement**

3a. `engine/db/schema.sql` — add to the `jobs` CREATE TABLE, right after the `language` line:

```sql
    geo_restriction TEXT,                      -- raw geo-restriction text detected (F2, UI)
    geo_scope       TEXT,                      -- normalized scope: iso2/region | worldwide | unknown | ''
    repost_count    INTEGER DEFAULT 0,         -- ghost-job signal: same company+core-title reposts in 90d
    liveness_checked_at TEXT,                  -- last liveness HTTP check (F2 hygiene)
```

3b. `engine/db/models.py::_migrate` — append after the `match_missing` line:

```python
        # F2: geo-scoring + pipeline hygiene columns.
        self._ensure_column("jobs", "geo_restriction", "TEXT")
        self._ensure_column("jobs", "geo_scope", "TEXT")
        self._ensure_column("jobs", "repost_count", "INTEGER DEFAULT 0")
        self._ensure_column("jobs", "liveness_checked_at", "TEXT")
```

3c. `upsert_job` INSERT — replace the statement + params so the geo fields persist:

```python
            self.conn.execute(
                """INSERT INTO jobs
                   (id, source, source_job_id, title, company, location, is_remote,
                    workplace_type, url, apply_url, description, employment_type,
                    salary_min, salary_max, salary_currency, salary_interval,
                    date_posted, language, geo_restriction, geo_scope,
                    raw_json, sources_json, state, discovered_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'discovered', ?)""",
                (
                    job.id,
                    job.source,
                    job.source_job_id,
                    job.title,
                    job.company,
                    job.location,
                    _b(job.is_remote),
                    job.workplace_type,
                    job.url,
                    job.apply_url,
                    job.description,
                    job.employment_type,
                    job.salary_min,
                    job.salary_max,
                    job.salary_currency,
                    job.salary_interval,
                    job.date_posted,
                    job.language,
                    job.geo_restriction,
                    job.geo_scope,
                    json.dumps(job.raw),
                    json.dumps([job.source]),
                    now,
                ),
            )
```

3d. `upsert_job` gap-fill UPDATE — add two SET lines right before `sources_json    = ?`:

```sql
                 geo_restriction = COALESCE(geo_restriction, ?),
                 geo_scope       = CASE WHEN COALESCE(geo_scope,'') IN ('','unknown')
                                        THEN ? ELSE geo_scope END,
```

…and add the matching params right before `json.dumps(sorted(sources))`:

```python
                job.geo_restriction,
                job.geo_scope,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_db_geo.py tests/test_engine.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/db/models.py tests/test_db_geo.py && rtk uv run ruff format engine/db/models.py tests/test_db_geo.py
rtk git add engine/db/models.py engine/db/schema.sql tests/test_db_geo.py
rtk git commit -m "feat(db): geo_restriction/geo_scope/repost_count/liveness columns on jobs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: New `Criteria` fields + seed frontmatter

**Files:**
- Modify: `engine/config.py` (`Criteria`, after `onsite_locations` block, ~line 36)
- Modify: `config/criteria.example.md`, `config/seeds/default/criteria.example.md`, `config/seeds/data/criteria.example.md`, `config/seeds/architecture/criteria.example.md`
- Test: `tests/test_geo_scoring.py` (created here; grows in Tasks 5–6)

**Interfaces:**
- Produces (read by Tasks 5, 9, 10, 12, 15):
  - `Criteria.candidate_country: str = ""` (ISO-2; empty = geo factor OFF)
  - `Criteria.acceptable_regions: list[str] = ["worldwide"]`
  - `Criteria.geo_penalty: float = 12.0`
  - `Criteria.re_apply_window_days: int = 0` (0 = off)

- [ ] **Step 1: Write the failing test**

Create `tests/test_geo_scoring.py`:

```python
"""Geo factor 2c + geo-mismatch 2d in the fit scorer (spec §5.2/§5.3). Fictional candidate."""

from __future__ import annotations

from engine.config import Criteria


def test_criteria_geo_defaults_are_off():
    c = Criteria()
    assert c.candidate_country == ""  # empty = geo factor OFF (never a real country default)
    assert c.acceptable_regions == ["worldwide"]
    assert c.geo_penalty == 12.0
    assert c.re_apply_window_days == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --group dev pytest tests/test_geo_scoring.py -v`
Expected: FAIL — `AttributeError: 'Criteria' object has no attribute 'candidate_country'`

- [ ] **Step 3: Implement**

3a. In `engine/config.py`, inside `class Criteria`, insert after the `onsite_locations` comment block (before `languages`):

```python
    # ── Geo-scoring (F2): where the candidate lives, for the remote-restriction penalty ──
    candidate_country: str = ""  # ISO-2 code (e.g. "ec"); empty = geo factor OFF.
    acceptable_regions: list[str] = Field(default_factory=lambda: ["worldwide"])
    # regions (latam/eu/na/apac/emea) whose geo-restricted remote jobs still work for you
    geo_penalty: float = 12.0  # points subtracted from a remote job restricted elsewhere
    re_apply_window_days: int = 0  # flag jobs at companies you applied to <N days ago; 0 = off
```

3b. Append the same block to the **frontmatter** of each of the four criteria example files (`config/criteria.example.md`, `config/seeds/default/criteria.example.md`, `config/seeds/data/criteria.example.md`, `config/seeds/architecture/criteria.example.md`) — insert just above the closing `---` fence:

```yaml
# ── Geo (F2): tu país, para la penalización de remotos restringidos ──
candidate_country: ""          # tu código ISO-2 (p. ej. "ec"); vacío = factor apagado
acceptable_regions: [worldwide] # regiones cuyos remotos restringidos sí te sirven (latam/eu/na/apac)
geo_penalty: 12                # puntos que resta un remoto restringido fuera de tu alcance
re_apply_window_days: 0        # marca empresas donde aplicaste hace <N días; 0 = apagado
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_geo_scoring.py tests/test_criteria_fields.py tests/test_frontmatter.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/config.py tests/test_geo_scoring.py && rtk uv run ruff format engine/config.py tests/test_geo_scoring.py
rtk git add engine/config.py tests/test_geo_scoring.py config/criteria.example.md config/seeds/default/criteria.example.md config/seeds/data/criteria.example.md config/seeds/architecture/criteria.example.md
rtk git commit -m "feat(criteria): candidate_country/acceptable_regions/geo_penalty/re_apply_window_days

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Factor 2c — geo penalty in `engine/scoring/fit.py`

**Files:**
- Modify: `engine/scoring/fit.py` (import ~line 15; new block after the 2b gate, after line 131)
- Test: `tests/test_geo_scoring.py` (extend)

**Interfaces:**
- Consumes: `geo_scope_covers` (Task 1), `Criteria.candidate_country/acceptable_regions/geo_penalty` (Task 4), `jobs.geo_scope/geo_restriction` (Task 3).
- Produces: knockout string prefix `"remoto restringido a "` (badge/UI greps for it) and a `score -= criteria.geo_penalty` that NEVER sets `disq`.

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_geo_scoring.py`:

```python
from engine.scoring.fit import score_job

# Fictional candidate: a data engineer living in a LatAm country ("xx" stand-ins avoided —
# we use "ec" as an EXAMPLE value in tests only; the code default is "" = off).
_GEO = Criteria(
    roles=["data engineer"],
    candidate_country="ec",
    acceptable_regions=["latam", "worldwide"],
    remote_required=True,
)


def _job(**kw) -> dict:
    base = {
        "title": "Data Engineer",
        "description": "python pipelines",
        "is_remote": 1,
        "workplace_type": "remote",
    }
    base.update(kw)
    return base


def test_us_only_remote_is_penalized_never_dq():
    restricted = score_job(_job(geo_scope="us", geo_restriction="Remote — US only"), _GEO)
    open_ = score_job(_job(geo_scope="worldwide"), _GEO)
    assert restricted.disqualified is False
    assert open_.score - restricted.score == 12.0
    assert any(k.startswith("remoto restringido a US") for k in restricted.knockouts)


def test_scope_in_acceptable_region_not_penalized():
    latam = score_job(_job(geo_scope="latam"), _GEO)
    own = score_job(_job(geo_scope="ec"), _GEO)
    open_ = score_job(_job(geo_scope="worldwide"), _GEO)
    assert latam.score == own.score == open_.score


def test_unknown_or_missing_scope_never_penalized():
    unknown = score_job(_job(geo_scope="unknown"), _GEO)
    missing = score_job(_job(), _GEO)  # no geo_scope key at all (pre-F2 rows)
    open_ = score_job(_job(geo_scope="worldwide"), _GEO)
    assert unknown.score == missing.score == open_.score


def test_factor_off_without_candidate_country():
    crit = Criteria(roles=["data engineer"], remote_required=True)  # candidate_country=""
    r = score_job(_job(geo_scope="us"), crit)
    assert not any("remoto restringido" in k for k in r.knockouts)


def test_geo_penalty_is_configurable():
    crit = Criteria(
        roles=["data engineer"],
        candidate_country="ec",
        acceptable_regions=["latam"],
        remote_required=True,
        geo_penalty=20.0,
    )
    restricted = score_job(_job(geo_scope="us"), crit)
    open_ = score_job(_job(geo_scope="worldwide"), crit)
    assert open_.score - restricted.score == 20.0


def test_onsite_job_ignores_geo_factor():
    crit = Criteria(roles=["data engineer"], candidate_country="ec", remote_required=False)
    r = score_job(
        {"title": "Data Engineer", "description": "x", "is_remote": 0, "geo_scope": ""}, crit
    )
    assert not any("remoto restringido" in k for k in r.knockouts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_geo_scoring.py -v`
Expected: FAIL — `test_us_only_remote_is_penalized_never_dq` (scores equal, no knockout)

- [ ] **Step 3: Implement in `engine/scoring/fit.py`**

3a. Add the import (with the other engine imports, after `from engine.config import Criteria`):

```python
from engine.geo import geo_scope_covers
```

3b. Insert after the 2b block (after `reasons.append(f"on-site outside your locations ...")`, line 131) and before section 3:

```python
    # 2c. Geo-restricted remote (F2): a remote posting restricted to a country/region that
    #     doesn't cover the candidate is penalized and flagged — NEVER disqualified (they
    #     stay browsable, just lower). Off when candidate_country is unset; "unknown"/""/
    #     "worldwide" scopes never penalize (no signal ≠ restriction).
    geo_scope = (job.get("geo_scope") or "").strip().lower()
    if (
        criteria.candidate_country
        and is_remote_job
        and geo_scope not in ("", "worldwide", "unknown")
        and not geo_scope_covers(
            geo_scope, criteria.candidate_country, criteria.acceptable_regions
        )
    ):
        score -= criteria.geo_penalty
        scope_label = ",".join(t.upper() for t in geo_scope.split(","))
        knockouts.append(f"remoto restringido a {scope_label}")
        raw = job.get("geo_restriction")
        reasons.append(
            f"remote restricted to {scope_label}"
            + (f' ("{raw}")' if raw else "")
            + " — outside your country/regions"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_geo_scoring.py tests/test_fit_domain.py tests/test_location.py tests/test_quality_gates.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/scoring/fit.py tests/test_geo_scoring.py && rtk uv run ruff format engine/scoring/fit.py tests/test_geo_scoring.py
rtk git add engine/scoring/fit.py tests/test_geo_scoring.py
rtk git commit -m "feat(scoring): factor 2c — penalize (never DQ) geo-restricted remote jobs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Factor 2d — remote/on-site contradiction flag (geo-mismatch)

**Files:**
- Modify: `engine/scoring/fit.py` (module-level regex near `_YEARS`, ~line 36; block right after factor 2c)
- Test: `tests/test_geo_scoring.py` (extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: knockout string prefix `'dice remoto pero: "'` with the quoted phrase. Flag only — no score change, no DQ.

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_geo_scoring.py`:

```python
def test_remote_flag_contradicted_by_office_days_is_flagged_with_quote():
    j = _job(description="Great python role. Note: 3 days in office per week required.")
    r = score_job(j, _GEO)
    hit = [k for k in r.knockouts if k.startswith("dice remoto pero")]
    assert hit and "3 days in office" in hit[0]
    assert r.disqualified is False


def test_remote_flag_contradicted_by_hybrid_wording():
    j = _job(description="We follow a hybrid model across our hubs.")
    r = score_job(j, _GEO)
    assert any(k.startswith("dice remoto pero") for k in r.knockouts)


def test_clean_remote_body_not_flagged():
    r = score_job(_job(description="fully remote, async-first python team"), _GEO)
    assert not any(k.startswith("dice remoto pero") for k in r.knockouts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_geo_scoring.py -k "dice or contradicted or clean_remote" -v`
Expected: FAIL — no `dice remoto pero` knockout produced

- [ ] **Step 3: Implement in `engine/scoring/fit.py`**

3a. Add the module-level regex (right after `_YEARS = ...`):

```python
# F2 geo-mismatch: phrases that contradict a "remote" flag. The matched phrase is quoted in
# the knockout so the user sees WHY ("3 days in office"). Flag-only — some postings mention
# "hybrid" innocently ("not a hybrid role"), so this never moves the score.
_OFFICE_DEMAND = re.compile(
    r"(\d\s*\+?\s*days?\s+(?:per\s+week\s+)?(?:in|at)(?:\s+the)?\s+office"
    r"|\d\s*d[ií]as\s+(?:por\s+semana\s+)?en\s+(?:la\s+)?oficina"
    r"|on[- ]?site\s+\d"
    r"|\bhybrid\b|\bh[ií]brido\b)",
    re.I,
)
```

3b. Insert right after the factor 2c block:

```python
    # 2d. Geo-mismatch (F2 hygiene): the metadata says remote but the body demands office
    #     presence. Flag with the exact quoted phrase; no score change (see regex comment).
    if is_remote_job and desc and (office_m := _OFFICE_DEMAND.search(desc)):
        quoted = office_m.group(0).strip()
        knockouts.append(f'dice remoto pero: "{quoted}"')
        reasons.append(f'flagged remote but body says "{quoted}"')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_geo_scoring.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/scoring/fit.py tests/test_geo_scoring.py && rtk uv run ruff format engine/scoring/fit.py tests/test_geo_scoring.py
rtk git add engine/scoring/fit.py tests/test_geo_scoring.py
rtk git commit -m "feat(scoring): factor 2d — flag remote postings whose body demands office days

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Repost/ghost detection — `engine/reposts.py` + penalty + runner hook

**Files:**
- Create: `engine/reposts.py`
- Modify: `engine/scoring/fit.py` (block 7b after the knockout section, after line 203)
- Modify: `engine/discovery/runner.py` (before `client.close()`, ~line 123)
- Test: `tests/test_reposts.py`

**Interfaces:**
- Consumes: `jobs.repost_count` column (Task 3), `norm_company`/`norm_text` from `engine.normalize`.
- Produces:
  - `core_title(title: str) -> str` — normalized title without seniority/modality tokens.
  - `sweep_reposts(db: DB, *, window_days: int = 90) -> int` — sets `jobs.repost_count`, returns how many rows got flagged.
  - fit.py: knockout prefix `"repost ("` + `score -= 4` when `repost_count >= 1`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reposts.py`:

```python
"""Repost/ghost-job detection (spec §5.3): same company + fuzzy-equal title, distinct ids."""

from __future__ import annotations

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job
from engine.reposts import core_title, sweep_reposts
from engine.scoring.fit import score_job


def test_core_title_strips_seniority_and_modality():
    assert core_title("Senior Data Engineer (Remote)") == "data engineer"
    assert core_title("Data Engineer II - Hybrid") == "data engineer"
    assert core_title("Staff Data Engineer") == "data engineer"


def test_sweep_flags_fuzzy_equal_titles_same_company(tmp_path):
    with DB(tmp_path / "atlas.db") as db:
        # Distinct natural keys (different locations) → distinct rows, same core identity.
        db.upsert_job(
            Job(source="greenhouse", title="Senior Data Engineer", company="Acme", location="Remote")
        )
        db.upsert_job(
            Job(source="lever", title="Data Engineer (Remote)", company="Acme Inc", location="Berlin")
        )
        db.upsert_job(
            Job(source="lever", title="Backend Engineer", company="Other Co", location="Remote")
        )
        flagged = sweep_reposts(db)
        rows = {r["title"]: r for r in db.list_jobs()}
    assert flagged == 2
    assert rows["Senior Data Engineer"]["repost_count"] == 1
    assert rows["Data Engineer (Remote)"]["repost_count"] == 1
    assert rows["Backend Engineer"]["repost_count"] == 0


def test_repost_penalty_and_flag_in_scoring():
    crit = Criteria(roles=["data engineer"], remote_required=False)
    base = {"title": "Data Engineer", "description": "python"}
    clean = score_job({**base, "repost_count": 0}, crit)
    reposted = score_job({**base, "repost_count": 2}, crit)
    assert clean.score - reposted.score == 4.0
    assert any(k.startswith("repost (") for k in reposted.knockouts)
    assert reposted.disqualified is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_reposts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.reposts'`

- [ ] **Step 3: Implement**

3a. Create `engine/reposts.py`:

```python
"""Repost / ghost-job detection (F2 hygiene, imported from career-ops).

A company that re-posts the SAME role (fuzzy-equal title: normalized, seniority and
modality words stripped) under new ids/URLs ≥2 times in 90 days smells like a ghost
posting or a perpetually-open req. We count the evidence into ``jobs.repost_count``;
the scorer applies a light −4 and the UI shows a badge. Deterministic, no network.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from engine.db.models import DB
from engine.normalize import norm_company, norm_text

# Seniority + modality + level-numbering tokens that vary across reposts of the same role.
_STRIP = re.compile(
    r"\b(senior|sr|junior|jr|lead|staff|principal|remote|remoto|hybrid|h[ií]brido|"
    r"on[- ]?site|onsite|presencial|ii|iii|iv)\b"
)
_WS = re.compile(r"\s+")


def core_title(title: str) -> str:
    """The role identity of a title: normalized, minus seniority/modality/level tokens."""
    base = norm_text(title)
    base = _STRIP.sub(" ", base)
    return _WS.sub(" ", base).strip()


def sweep_reposts(db: DB, *, window_days: int = 90) -> int:
    """Recount reposts over the window and persist ``repost_count`` per job.

    repost_count = (# distinct postings of the same company+core_title in the window) − 1,
    so 0 means unique and ≥1 means "seen re-posted". Idempotent: recomputed from scratch
    for every job discovered inside the window (stale rows outside it are left alone).
    Returns how many rows carry a flag (repost_count ≥ 1) after the sweep.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
    rows = db.conn.execute(
        "SELECT id, company, title FROM jobs WHERE discovered_at >= ?", (cutoff,)
    ).fetchall()
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in rows:
        key = (norm_company(r["company"]), core_title(r["title"]))
        if key[1]:  # a title made only of stripped tokens has no identity — skip
            groups[key].add(r["id"])
    flagged = 0
    for ids in groups.values():
        repost = len(ids) - 1 if len(ids) >= 2 else 0
        for jid in ids:
            db.conn.execute("UPDATE jobs SET repost_count=? WHERE id=?", (repost, jid))
        flagged += len(ids) if repost else 0
    db.conn.commit()
    return flagged
```

3b. `engine/scoring/fit.py` — insert after the knockout block (section 7, after `reasons.append(f"knockout flags: ...")`, line 203):

```python
    # 7b. Repost/ghost signal (F2 hygiene): the same company re-posted this fuzzy-equal
    #     title with new ids ≥2× in 90 days (see engine/reposts.py). Light, visible nudge.
    repost_count = int(job.get("repost_count") or 0)
    if repost_count >= 1:
        score -= 4
        knockouts.append(f"repost ({repost_count}x en 90 días)")
        reasons.append(f"reposted {repost_count}x in 90 days (possible ghost posting)")
```

3c. `engine/discovery/runner.py` — insert right before `client.close()` (line 123):

```python
    # F2 hygiene: recount repost/ghost evidence over the fresh inventory (no network).
    from engine.reposts import sweep_reposts

    summary["reposts_flagged"] = sweep_reposts(db)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_reposts.py tests/test_geo_scoring.py tests/test_engine.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/reposts.py engine/scoring/fit.py engine/discovery/runner.py tests/test_reposts.py && rtk uv run ruff format engine/reposts.py engine/scoring/fit.py engine/discovery/runner.py tests/test_reposts.py
rtk git add engine/reposts.py engine/scoring/fit.py engine/discovery/runner.py tests/test_reposts.py
rtk git commit -m "feat(hygiene): repost/ghost detection sweep + light score penalty + badge data

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Liveness gate — `engine/discovery/liveness.py` + `expired` state

**Files:**
- Create: `engine/discovery/liveness.py`
- Modify: `engine/normalize.py` (`STATES` list, line 15–30)
- Test: `tests/test_liveness.py`

**Interfaces:**
- Consumes: `jobs.liveness_checked_at` (Task 3), `DB.set_state`, `engine.discovery.http.make_client`.
- Produces:
  - `"expired"` appended to `engine.normalize.STATES` (col-less state, like `dismissed`).
  - `check_url(client: httpx.Client, url: str) -> tuple[str, str]` — `("alive"|"dead"|"unknown", reason)`.
  - `sweep_liveness(db: DB, *, limit: int = 40, client: httpx.Client | None = None, delay_s: float = 0.5) -> dict` — `{"checked": int, "expired": int, "unknown": int}`.
  - `SWEEP_STATES: tuple[str, ...]` — the pre-applied states eligible for expiry.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_liveness.py`:

```python
"""Liveness gate (spec §5.3): deterministic HTTP checks; ambiguity NEVER expires a job."""

from __future__ import annotations

import httpx

from engine.db.models import DB
from engine.discovery.liveness import check_url, sweep_liveness
from engine.normalize import STATES, Job


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_expired_is_a_valid_state():
    assert "expired" in STATES


def test_404_and_410_are_dead():
    with _client(lambda req: httpx.Response(404)) as c:
        assert check_url(c, "https://x.co/jobs/1") == ("dead", "http 404")
    with _client(lambda req: httpx.Response(410)) as c:
        assert check_url(c, "https://x.co/jobs/1") == ("dead", "http 410")


def test_tombstone_phrases_multilanguage():
    for phrase in (
        "This position has been filled.",
        "Sorry, this job is no longer available.",
        "Esta oferta ya no está disponible.",
        "Cette offre n'est plus disponible.",
    ):
        with _client(lambda req, p=phrase: httpx.Response(200, text=f"<html>{p}</html>")) as c:
            verdict, reason = check_url(c, "https://x.co/jobs/1")
        assert verdict == "dead", phrase
        assert "tombstone" in reason


def test_redirect_to_careers_root_is_dead():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/jobs/123":
            return httpx.Response(302, headers={"location": "https://x.co/careers"})
        return httpx.Response(200, text="<html>Open roles at X</html>")

    with _client(handler) as c:
        verdict, reason = check_url(c, "https://x.co/jobs/123")
    assert verdict == "dead" and "careers root" in reason


def test_alive_and_ambiguous_cases():
    with _client(lambda req: httpx.Response(200, text="<html>Apply now! Great role.</html>")) as c:
        assert check_url(c, "https://x.co/jobs/1")[0] == "alive"
    with _client(lambda req: httpx.Response(500)) as c:
        assert check_url(c, "https://x.co/jobs/1")[0] == "unknown"

    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=req)

    with _client(boom) as c:
        assert check_url(c, "https://x.co/jobs/1")[0] == "unknown"


def test_sweep_expires_dead_keeps_alive_and_stamps_checked_at(tmp_path):
    def handler(req: httpx.Request) -> httpx.Response:
        if "dead" in str(req.url):
            return httpx.Response(404)
        return httpx.Response(200, text="Apply now")

    with DB(tmp_path / "atlas.db") as db:
        db.upsert_job(
            Job(source="lever", title="DE A", company="Acme", url="https://x.co/jobs/dead")
        )
        db.upsert_job(
            Job(source="lever", title="DE B", company="Beta", url="https://x.co/jobs/alive")
        )
        with _client(handler) as c:
            out = sweep_liveness(db, limit=10, client=c, delay_s=0)
        rows = {r["title"]: r for r in db.list_jobs(states=list(STATES))}
    assert out == {"checked": 2, "expired": 1, "unknown": 0}
    assert rows["DE A"]["state"] == "expired"
    assert rows["DE B"]["state"] == "discovered"
    assert rows["DE A"]["liveness_checked_at"] and rows["DE B"]["liveness_checked_at"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_liveness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.discovery.liveness'`

- [ ] **Step 3: Implement**

3a. `engine/normalize.py` — append to `STATES` (after the `"dismissed"` entry and its comment):

```python
    "expired",  # liveness gate: the posting 404s / is filled — out of the board, restorable via
    # the "expirados" filter. Col-less like `dismissed`; set only by engine/discovery/liveness.py.
```

3b. Create `engine/discovery/liveness.py`:

```python
"""Liveness gate (F2 hygiene, imported from career-ops): is a stored posting still live?

Deterministic HTTP checks only — 404/410, tombstone phrases (multi-language) and a
redirect back to a careers root all mean the vacancy is gone → state ``expired``.
Anything ambiguous (5xx, timeouts, transport errors) is 'unknown' and NEVER expires
a job: false-expiring a live posting costs an application; a dead one lingering costs
nothing. $0 and keyless, like the rest of the engine.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

import httpx

from engine.db.models import DB
from engine.discovery.http import make_client
from engine.normalize import now_iso

DEAD_STATUSES = frozenset({404, 410})

_DEAD_PHRASES = re.compile(
    r"(job (?:posting |opening )?(?:is )?no longer (?:available|active|open)"
    r"|no longer accepting applications"
    r"|position has been filled"
    r"|job (?:posting )?not found"
    r"|posting (?:has )?expired"
    r"|this job is (?:closed|expired)"
    r"|esta (?:oferta|vacante|posici[oó]n) ya no est[aá] disponible"
    r"|la vacante (?:fue cerrada|ya no existe)"
    r"|oferta caducada"
    r"|cette offre n(?:'|’)est plus disponible"
    r"|stelle ist nicht mehr verf[uü]gbar"
    r"|vaga (?:encerrada|expirada))",
    re.I,
)

# Only pre-application states are expirable: later stages carry human work we never discard.
SWEEP_STATES: tuple[str, ...] = (
    "discovered",
    "scored",
    "shortlisted",
    "tailored",
    "drafted",
    "ready",
)


def check_url(client: httpx.Client, url: str) -> tuple[str, str]:
    """('alive' | 'dead' | 'unknown', reason). GET, not HEAD — many ATSes reject HEAD."""
    try:
        resp = client.get(url)
    except httpx.HTTPError as e:
        return "unknown", type(e).__name__
    if resp.status_code in DEAD_STATUSES:
        return "dead", f"http {resp.status_code}"
    if resp.status_code >= 400:
        return "unknown", f"http {resp.status_code}"
    if resp.history:  # redirected — a bounce to the careers root is a tombstone
        final_segments = [s for s in urlsplit(str(resp.url)).path.split("/") if s]
        if len(final_segments) <= 1:
            return "dead", f"redirected to careers root ({resp.url})"
    m = _DEAD_PHRASES.search(resp.text[:200_000])
    if m:
        return "dead", f'tombstone phrase: "{m.group(0)}"'
    return "alive", "ok"


def sweep_liveness(
    db: DB, *, limit: int = 40, client: httpx.Client | None = None, delay_s: float = 0.5
) -> dict:
    """Check the least-recently-checked active jobs with a URL; expire the dead ones.

    Rate-limited (``delay_s`` between requests — never hammer an ATS). Every checked job
    gets ``liveness_checked_at`` stamped so successive sweeps rotate through the inventory.
    """
    owns_client = client is None
    client = client or make_client(timeout=10)
    placeholders = ",".join("?" * len(SWEEP_STATES))
    rows = db.conn.execute(
        f"SELECT id, url FROM jobs WHERE state IN ({placeholders}) AND url IS NOT NULL "
        "ORDER BY COALESCE(liveness_checked_at, '') ASC, discovered_at ASC LIMIT ?",
        (*SWEEP_STATES, int(limit)),
    ).fetchall()
    out = {"checked": 0, "expired": 0, "unknown": 0}
    try:
        for i, r in enumerate(rows):
            if i and delay_s:
                time.sleep(delay_s)
            verdict, reason = check_url(client, r["url"])
            db.conn.execute(
                "UPDATE jobs SET liveness_checked_at=? WHERE id=?", (now_iso(), r["id"])
            )
            db.conn.commit()
            out["checked"] += 1
            if verdict == "dead":
                db.set_state(r["id"], "expired", {"reason": reason, "via": "liveness"})
                out["expired"] += 1
            elif verdict == "unknown":
                out["unknown"] += 1
    finally:
        if owns_client:
            client.close()
    return out
```

- [ ] **Step 4: Run tests to verify they pass (STATES change can ripple — run the engine suite too)**

Run: `rtk uv run --group dev pytest tests/test_liveness.py tests/test_engine.py tests/test_backend_api.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/discovery/liveness.py engine/normalize.py tests/test_liveness.py && rtk uv run ruff format engine/discovery/liveness.py engine/normalize.py tests/test_liveness.py
rtk git add engine/discovery/liveness.py engine/normalize.py tests/test_liveness.py
rtk git commit -m "feat(hygiene): liveness gate — HTTP dead-posting detection + expired state

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: `POST /api/liveness/sweep` + opt-in sweep at the end of discover

**Files:**
- Modify: `dashboard/backend/main.py` (new block after the discover endpoints, ~line 373)
- Modify: `engine/discovery/runner.py` (after the adzuna block, before the repost sweep from Task 7)
- Modify: `config/sources.yaml`, `config/seeds/default/sources.yaml`, `config/seeds/data/sources.yaml`, `config/seeds/architecture/sources.yaml`
- Test: `tests/test_liveness_api.py`

**Interfaces:**
- Consumes: `sweep_liveness` / `check_url` (Task 8), `require_trusted_origin`, the plan-019 background pattern (`_DISCOVER_LOCK` idiom).
- Produces: `POST /api/liveness/sweep?limit=N` → `{"started": bool, "running"?: bool}`; `GET /api/liveness/status` → `{"running": bool}`; `sources.yaml` key `liveness: {enabled: false, limit: 40}` honored by `discover()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_liveness_api.py`:

```python
"""POST /api/liveness/sweep: origin-guarded, background, expires dead jobs."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_job(url: str) -> str:
    from engine.db.models import DB
    from engine.normalize import Job

    with DB() as db:
        db.upsert_job(Job(source="lever", title="Data Scientist", company="Acme", url=url))
        return db.list_jobs()[0]["id"]


def test_sweep_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        resp = client.post(
            "/api/liveness/sweep", headers={"origin": "https://evil.example.com"}
        )
    assert resp.status_code == 403


def test_sweep_expires_dead_jobs(atlas_app, monkeypatch):
    import engine.discovery.liveness as liveness
    from engine.db.models import DB

    monkeypatch.setattr(liveness, "check_url", lambda client, url: ("dead", "http 404"))
    with TestClient(atlas_app) as client:  # TestClient runs BackgroundTasks on exit of request
        jid = _seed_job("https://x.co/jobs/1")
        resp = client.post("/api/liveness/sweep")
        assert resp.status_code == 200 and resp.json()["started"] is True
        status = client.get("/api/liveness/status").json()
        assert "running" in status
    with DB() as db:
        assert db.get_job(jid)["state"] == "expired"


def test_discover_runs_liveness_only_when_enabled(tmp_path, monkeypatch):
    from engine.db.models import DB
    from engine.discovery import runner

    calls: list[int] = []
    monkeypatch.setattr(
        "engine.discovery.liveness.sweep_liveness",
        lambda db, limit=40, client=None: calls.append(limit) or {"checked": 0},
    )
    cfg_off = {"ats": {"enabled": False}, "jobspy": {"enabled": False},
               "himalayas": {"enabled": False}, "adzuna": {"enabled": False}}
    with DB(tmp_path / "a.db") as db:
        runner.discover(db, sources_cfg=cfg_off, companies=[], terms=[])
        assert calls == []  # default: off
        runner.discover(
            db,
            sources_cfg={**cfg_off, "liveness": {"enabled": True, "limit": 7}},
            companies=[],
            terms=[],
        )
        assert calls == [7]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_liveness_api.py -v`
Expected: FAIL — 404 on `/api/liveness/sweep`, and `calls == []` assertion on the enabled run

- [ ] **Step 3: Implement**

3a. `dashboard/backend/main.py` — insert after `api_discover_status` (line 373), mirroring the plan-019 pattern:

```python
# ── Liveness sweep (F2 hygiene) — same fire-and-forget model as /api/discover ─
_LIVENESS_LOCK = Lock()
_liveness_running = False


def _run_liveness_sweep(limit: int, profile_id: str | None) -> None:
    global _liveness_running
    try:
        from engine.discovery.liveness import sweep_liveness

        if profile_id is not None:
            paths.set_profile(profile_id)
        with DB() as db:  # own short-lived connection — never holds the API lock on network
            sweep_liveness(db, limit=limit)
    except Exception as e:  # noqa: BLE001 — record the failure instead of dropping it silently
        try:
            with DB() as db:
                db.log_event(None, "error", {"stage": "liveness_bg", "error": str(e)[:200]})
        except Exception:  # noqa: BLE001
            pass
    finally:
        with _LIVENESS_LOCK:
            _liveness_running = False


@app.post("/api/liveness/sweep", dependencies=[Depends(require_trusted_origin)])
def api_liveness_sweep(background: BackgroundTasks, limit: int = 40):
    """Expire dead postings (404/410/tombstone) in the background. One sweep at a time."""
    global _liveness_running
    with _LIVENESS_LOCK:
        if _liveness_running:
            return {"started": False, "running": True}
        _liveness_running = True
    background.add_task(_run_liveness_sweep, max(1, min(int(limit), 200)), paths.PROFILE_ID)
    return {"started": True}


@app.get("/api/liveness/status")
def api_liveness_status():
    with _LIVENESS_LOCK:
        return {"running": _liveness_running}
```

3b. `engine/discovery/runner.py` — insert after the adzuna block (line 122), BEFORE the repost sweep added in Task 7 (final order: adzuna → liveness → reposts → `client.close()`):

```python
    # F2 hygiene (opt-in via sources.yaml): expire dead postings at the end of a discover.
    lv = cfg.get("liveness", {})
    if want("liveness") and lv.get("enabled", False):
        from engine.discovery.liveness import sweep_liveness

        summary["liveness"] = sweep_liveness(db, limit=int(lv.get("limit", 40)), client=client)
```

3c. Append to `config/sources.yaml` AND `config/seeds/{default,data,architecture}/sources.yaml`:

```yaml
# F2: liveness gate — expire dead postings (404/tombstone) at the end of each discover.
# Off by default (adds N HTTP calls per run); always available on demand from the web UI
# via POST /api/liveness/sweep.
liveness:
  enabled: false
  limit: 40
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_liveness_api.py tests/test_backend_api.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check dashboard/backend/main.py engine/discovery/runner.py tests/test_liveness_api.py && rtk uv run ruff format dashboard/backend/main.py engine/discovery/runner.py tests/test_liveness_api.py
rtk git add dashboard/backend/main.py engine/discovery/runner.py tests/test_liveness_api.py config/sources.yaml config/seeds/default/sources.yaml config/seeds/data/sources.yaml config/seeds/architecture/sources.yaml
rtk git commit -m "feat(hygiene): background liveness sweep endpoint + opt-in discover hook

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Re-apply window flag in `engine/scoring/run.py`

**Files:**
- Modify: `engine/scoring/run.py`
- Test: `tests/test_reapply_window.py`

**Interfaces:**
- Consumes: `Criteria.re_apply_window_days` (Task 4), `jobs.applied_at`, `norm_company`.
- Produces: `_recently_applied_companies(db: DB, window_days: int) -> dict[str, int]` (norm company → days since most recent own application); knockout prefix `"aplicaste a esta empresa hace "` appended by `score_jobs` (informative — no score change, no DQ).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reapply_window.py`:

```python
"""Re-apply window (spec §5.3): flag — never hide — companies with a recent own application."""

from __future__ import annotations

import json

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job
from engine.scoring.run import _recently_applied_companies, score_jobs


def _seed(db: DB, title: str, company: str, applied: bool = False) -> str:
    db.upsert_job(
        Job(source="lever", title=title, company=company, description="python data")
    )
    jid = next(j["id"] for j in db.list_jobs() if j["title"] == title)
    if applied:
        db.set_state(jid, "applied")
    return jid


def test_recently_applied_companies_windowing(tmp_path):
    with DB(tmp_path / "a.db") as db:
        _seed(db, "Data Engineer", "Acme Inc", applied=True)
        _seed(db, "ML Engineer", "Other Co")
        recent = _recently_applied_companies(db, 14)
    assert "acme" in recent and recent["acme"] == 0  # applied today → 0 days ago
    assert "other co" not in recent


def test_new_job_at_recently_applied_company_gets_flag(tmp_path):
    crit = Criteria(roles=["data engineer"], remote_required=False, re_apply_window_days=14)
    with DB(tmp_path / "a.db") as db:
        _seed(db, "Data Engineer", "Acme", applied=True)
        fresh = _seed(db, "Senior Data Engineer", "Acme")
        score_jobs(db, crit)
        row = db.get_job(fresh)
        flags = json.loads(row["knockout_flags"] or "[]")
        applied_row = db.get_job(_seed(db, "Data Engineer", "Acme"))  # same id, already applied
    assert any(f.startswith("aplicaste a esta empresa hace") for f in flags)
    assert applied_row["state"] == "applied"  # the applied job itself is never re-flagged


def test_window_off_by_default(tmp_path):
    crit = Criteria(roles=["data engineer"], remote_required=False)  # re_apply_window_days=0
    with DB(tmp_path / "a.db") as db:
        _seed(db, "Data Engineer", "Acme", applied=True)
        fresh = _seed(db, "Senior Data Engineer", "Acme")
        score_jobs(db, crit)
        flags = json.loads(db.get_job(fresh)["knockout_flags"] or "[]")
    assert not any(f.startswith("aplicaste a") for f in flags)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_reapply_window.py -v`
Expected: FAIL — `ImportError: cannot import name '_recently_applied_companies'`

- [ ] **Step 3: Implement in `engine/scoring/run.py`**

3a. Extend the imports:

```python
from datetime import UTC, datetime, timedelta
```

3b. Add the helper above `score_jobs`:

```python
def _recently_applied_companies(db: DB, window_days: int) -> dict[str, int]:
    """norm_company → days since YOUR most recent application to it, within the window.

    Powers the re-apply window (F2): discovery keeps showing these jobs, the scorer only
    FLAGS them ("aplicaste hace N días") so you don't burn a fresh application too soon.
    """
    if window_days <= 0:
        return {}
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=window_days)
    out: dict[str, int] = {}
    rows = db.conn.execute(
        "SELECT company, applied_at FROM jobs WHERE applied_at IS NOT NULL"
    ).fetchall()
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["applied_at"])
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if dt < cutoff:
            continue
        days = int((now - dt).total_seconds() // 86400)
        comp = norm_company(r["company"])
        if comp and (comp not in out or days < out[comp]):
            out[comp] = days
    return out
```

3c. In `score_jobs`, load the map once (after the `learn_map` loop):

```python
    recent_applied = _recently_applied_companies(db, criteria.re_apply_window_days)
```

…and inside the per-job loop, right after `res = score_job(...)` and before `db.set_fit(...)`:

```python
        if recent_applied and not j.get("applied_at"):
            days = recent_applied.get(norm_company(j.get("company", "")))
            if days is not None:
                res.knockouts.append(f"aplicaste a esta empresa hace {days} días")
                res.reasons.append(
                    f"re-apply window: own application {days}d ago "
                    f"(<{criteria.re_apply_window_days}d)"
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_reapply_window.py tests/test_engine.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/scoring/run.py tests/test_reapply_window.py && rtk uv run ruff format engine/scoring/run.py tests/test_reapply_window.py
rtk git add engine/scoring/run.py tests/test_reapply_window.py
rtk git commit -m "feat(scoring): informative re-apply-window flag per company

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Posting snapshot on Applied (`posting_snapshots` table)

**Files:**
- Modify: `engine/db/schema.sql` (append table at end)
- Modify: `engine/db/models.py` (new methods after `set_state`, ~line 222)
- Modify: `dashboard/backend/main.py` (`api_set_state` line ~273, `api_mark_applied` line ~284)
- Test: `tests/test_snapshots.py`

**Interfaces:**
- Consumes: existing `jobs` row, `now_iso`.
- Produces:
  - Table `posting_snapshots(id, job_id, captured_at, payload)` (payload = JSON).
  - `DB.snapshot_posting(job_id: str) -> int | None` — idempotent (one snapshot per job; returns None on duplicate/unknown job).
  - `DB.snapshots_for(job_id: str) -> list[dict]` — payload parsed into `payload` key.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_snapshots.py`:

```python
"""Posting archive (spec §5.3): snapshot the posting when you apply, as evidence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from engine.db.models import DB
from engine.normalize import Job


def _seed() -> str:
    with DB() as db:
        db.upsert_job(
            Job(
                source="greenhouse",
                title="Data Scientist",
                company="Acme",
                url="https://x.co/jobs/1",
                description="Build models.",
                salary_min=90000.0,
            )
        )
        return db.list_jobs()[0]["id"]


def test_snapshot_posting_is_idempotent(tmp_path):
    with DB(tmp_path / "a.db") as db:
        db.upsert_job(Job(source="lever", title="DE", company="Acme", description="x"))
        jid = db.list_jobs()[0]["id"]
        first = db.snapshot_posting(jid)
        second = db.snapshot_posting(jid)
        snaps = db.snapshots_for(jid)
    assert first is not None and second is None
    assert len(snaps) == 1
    assert snaps[0]["payload"]["title"] == "DE"
    assert snaps[0]["captured_at"]


def test_mark_applied_persists_snapshot(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed()
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200
        assert client.post(f"/api/jobs/{jid}/applied").status_code == 200  # re-POST: still one
    with DB() as db:
        snaps = db.snapshots_for(jid)
    assert len(snaps) == 1
    assert snaps[0]["payload"]["company"] == "Acme"
    assert snaps[0]["payload"]["salary_min"] == 90000.0


def test_state_transition_to_applied_also_snapshots(atlas_app):
    with TestClient(atlas_app) as client:
        jid = _seed()
        client.post(f"/api/jobs/{jid}/state", json={"state": "applied"})
    with DB() as db:
        assert len(db.snapshots_for(jid)) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_snapshots.py -v`
Expected: FAIL — `AttributeError: 'DB' object has no attribute 'snapshot_posting'`

- [ ] **Step 3: Implement**

3a. Append to `engine/db/schema.sql`:

```sql
-- Posting archive (F2 hygiene): an immutable snapshot of the posting captured when the
-- user marks Applied — evidence for prep/negotiation even after the posting dies.
CREATE TABLE IF NOT EXISTS posting_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    captured_at TEXT NOT NULL,
    payload     TEXT NOT NULL                      -- json: title/company/location/description/salary/url/date_posted
);
CREATE INDEX IF NOT EXISTS idx_snapshots_job ON posting_snapshots(job_id);
```

3b. `engine/db/models.py` — add after `counts_by_state` (before the cv-versions section):

```python
    # ── posting snapshots (F2) ────────────────────────────────────────────────
    _SNAPSHOT_FIELDS = (
        "title", "company", "location", "description", "url", "apply_url",
        "salary_min", "salary_max", "salary_currency", "salary_interval", "date_posted",
    )

    def snapshot_posting(self, job_id: str) -> int | None:
        """Persist an immutable snapshot of the posting at apply time. Idempotent per job."""
        if self.conn.execute(
            "SELECT 1 FROM posting_snapshots WHERE job_id=? LIMIT 1", (job_id,)
        ).fetchone():
            return None
        job = self.get_job(job_id)
        if not job:
            return None
        payload = {k: job.get(k) for k in self._SNAPSHOT_FIELDS}
        cur = self.conn.execute(
            "INSERT INTO posting_snapshots (job_id, captured_at, payload) VALUES (?,?,?)",
            (job_id, now_iso(), json.dumps(payload)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def snapshots_for(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM posting_snapshots WHERE job_id=? ORDER BY captured_at", (job_id,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = _loads(d.get("payload"), {})
            out.append(d)
        return out
```

3c. `dashboard/backend/main.py` — in `api_set_state`, extend the applied branch:

```python
    if body.state == "applied":
        db.snapshot_posting(job_id)  # archive the posting as evidence (F2)
        followups.schedule(db, job_id, channel="email")
```

…and in `api_mark_applied`, before `followups.schedule(...)`:

```python
    db.snapshot_posting(job_id)  # archive the posting as evidence (F2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_snapshots.py tests/test_backend_api.py -v`
Expected: all pass

- [ ] **Step 5: Lint + commit**

```bash
rtk uv run ruff check engine/db/models.py dashboard/backend/main.py tests/test_snapshots.py && rtk uv run ruff format engine/db/models.py dashboard/backend/main.py tests/test_snapshots.py
rtk git add engine/db/schema.sql engine/db/models.py dashboard/backend/main.py tests/test_snapshots.py
rtk git commit -m "feat(hygiene): archive posting snapshot when a job is marked applied

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: `save_criteria()` + `GET/PUT /api/criteria`

**Files:**
- Modify: `engine/config.py` (after `load_criteria`, ~line 121)
- Modify: `dashboard/backend/main.py` (new body model near the others ~line 190; endpoints after the settings section ~line 492)
- Test: `tests/test_criteria_save.py`, `tests/test_criteria_api.py`

**Interfaces:**
- Consumes: `Criteria` (Task 4), `_split_frontmatter`, `paths.CRITERIA_PATH` (late-read), `require_trusted_origin`.
- Produces:
  - `criteria_to_markdown(criteria: Criteria) -> str` — frontmatter + prose document.
  - `save_criteria(criteria: Criteria) -> Path` — writes the ACTIVE profile's `criteria.md` (never the `.example`).
  - `GET /api/criteria` → `{"criteria": {<frontmatter fields>}, "prose": str}`.
  - `PUT /api/criteria` (origin-guarded) with body `{"criteria": dict, "prose": str}` → validates with `Criteria`, persists, returns `{"ok": True, "path": str}`; 422 on invalid fields.

- [ ] **Step 1: Write the failing engine tests**

Create `tests/test_criteria_save.py`:

```python
"""criteria.md writer: frontmatter round-trips through the Criteria model (F2 wizard)."""

from __future__ import annotations

import engine.paths as paths
from engine.config import Criteria, criteria_to_markdown, load_criteria, save_criteria


def test_markdown_has_frontmatter_and_prose():
    c = Criteria(roles=["data engineer"], candidate_country="ec", prose="# Mi búsqueda\nTexto.")
    md = criteria_to_markdown(c)
    assert md.startswith("---\n")
    assert "candidate_country: ec" in md
    assert md.rstrip().endswith("Texto.")
    assert "prose:" not in md  # prose is the body, never a frontmatter key


def test_save_and_reload_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "config" / "criteria.md")
    c = Criteria(
        roles=["data engineer"],
        candidate_country="ec",
        acceptable_regions=["latam"],
        geo_penalty=15.0,
        re_apply_window_days=14,
        prose="# Mi búsqueda",
    )
    written = save_criteria(c)
    assert written == tmp_path / "config" / "criteria.md" and written.exists()
    c2 = load_criteria()
    assert c2.roles == ["data engineer"]
    assert c2.candidate_country == "ec"
    assert c2.acceptable_regions == ["latam"]
    assert c2.geo_penalty == 15.0
    assert c2.re_apply_window_days == 14
    assert "Mi búsqueda" in c2.prose
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_criteria_save.py -v`
Expected: FAIL — `ImportError: cannot import name 'criteria_to_markdown'`

- [ ] **Step 3: Implement the engine side (`engine/config.py`, after `load_criteria`)**

```python
def criteria_to_markdown(criteria: Criteria) -> str:
    """Serialize a Criteria back to the hybrid criteria.md format (frontmatter + prose)."""
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
```

Also add the import at the top of `engine/config.py` (with the other stdlib imports, before `from typing import Any`):

```python
from pathlib import Path
```

- [ ] **Step 4: Run engine tests**

Run: `rtk uv run --group dev pytest tests/test_criteria_save.py tests/test_frontmatter.py -v`
Expected: all pass

- [ ] **Step 5: Write the failing API tests**

Create `tests/test_criteria_api.py`:

```python
"""GET/PUT /api/criteria: the wizard's read/write path for the active profile's criteria."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _redirect_criteria(monkeypatch, tmp_path):
    import engine.paths as paths

    monkeypatch.setattr(paths, "CRITERIA_PATH", tmp_path / "config" / "criteria.md")


def test_get_criteria_returns_fields_and_prose(atlas_app, tmp_path, monkeypatch):
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        resp = client.get("/api/criteria")
    assert resp.status_code == 200
    body = resp.json()
    assert "candidate_country" in body["criteria"]
    assert "prose" not in body["criteria"]
    assert isinstance(body["prose"], str)


def test_put_criteria_roundtrip(atlas_app, tmp_path, monkeypatch):
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        got = client.get("/api/criteria").json()
        got["criteria"]["candidate_country"] = "ec"
        got["criteria"]["acceptable_regions"] = ["latam", "worldwide"]
        got["criteria"]["roles"] = ["data engineer"]
        resp = client.put(
            "/api/criteria", json={"criteria": got["criteria"], "prose": "# Mi búsqueda"}
        )
        assert resp.status_code == 200 and resp.json()["ok"] is True
        again = client.get("/api/criteria").json()
    assert again["criteria"]["candidate_country"] == "ec"
    assert again["criteria"]["acceptable_regions"] == ["latam", "worldwide"]
    assert "Mi búsqueda" in again["prose"]
    assert (tmp_path / "config" / "criteria.md").exists()


def test_put_criteria_rejects_invalid_payload(atlas_app, tmp_path, monkeypatch):
    _redirect_criteria(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        resp = client.put(
            "/api/criteria", json={"criteria": {"geo_penalty": "not-a-number"}, "prose": ""}
        )
    assert resp.status_code == 422


def test_put_criteria_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        resp = client.put(
            "/api/criteria",
            json={"criteria": {}, "prose": ""},
            headers={"origin": "https://evil.example.com"},
        )
    assert resp.status_code == 403
```

- [ ] **Step 6: Run API tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_criteria_api.py -v`
Expected: FAIL — 404/405 on `/api/criteria`

- [ ] **Step 7: Implement the endpoints (`dashboard/backend/main.py`)**

7a. Add the body model with the other `BaseModel`s (~line 190):

```python
class CriteriaBody(BaseModel):
    criteria: dict
    prose: str = ""
```

7b. Add the endpoints after the settings section (after `api_csv_columns`):

```python
# ── Criteria (F2 wizard): read/write the active profile's criteria.md frontmatter ─
@app.get("/api/criteria")
def api_get_criteria():
    from engine.config import load_criteria

    c = load_criteria()
    return {"criteria": c.model_dump(exclude={"prose"}), "prose": c.prose}


@app.put("/api/criteria", dependencies=[Depends(require_trusted_origin)])
def api_put_criteria(body: CriteriaBody):
    from pydantic import ValidationError

    from engine.config import Criteria, save_criteria

    try:
        c = Criteria(**{**body.criteria, "prose": body.prose})
    except ValidationError as e:
        raise HTTPException(422, str(e)) from None
    path = save_criteria(c)
    return {"ok": True, "path": str(path)}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_criteria_api.py tests/test_criteria_save.py tests/test_backend_api.py -v`
Expected: all pass

- [ ] **Step 9: Lint + commit**

```bash
rtk uv run ruff check engine/config.py dashboard/backend/main.py tests/test_criteria_save.py tests/test_criteria_api.py && rtk uv run ruff format engine/config.py dashboard/backend/main.py tests/test_criteria_save.py tests/test_criteria_api.py
rtk git add engine/config.py dashboard/backend/main.py tests/test_criteria_save.py tests/test_criteria_api.py
rtk git commit -m "feat(onboarding): GET/PUT /api/criteria backed by save_criteria round-trip

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: `POST /api/cv/import` (multipart upload → reviewable draft)

**Files:**
- Modify: `pyproject.toml` (dependencies list)
- Modify: `dashboard/backend/main.py` (endpoint after `api_cv_library`, ~line 461)
- Test: `tests/test_cv_import_api.py`

**Interfaces:**
- Consumes: `engine.cv.import_cv.{SUPPORTED, extract_text, build_draft}` (unchanged), `profiles.domain_of`, `paths.INBOX_DIR` / `paths.MASTER_CV_PATH` (late-read), `UploadFile` (needs `python-multipart`).
- Produces: `POST /api/cv/import` (origin-guarded, multipart field `file`) → `{"ok": True, "draft": str, "path": str, "chars": int}`; 400 on unsupported format / empty extraction. Writes `master_cv.draft.yaml` next to the profile's `master_cv.yaml` — NEVER touches `master_cv.yaml` itself.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, append to the `dependencies` list (after `"pdfplumber>=0.11",`):

```toml
    "python-multipart>=0.0.9", # FastAPI UploadFile parsing (POST /api/cv/import)
```

Run: `rtk proxy uv sync`
Expected: `python-multipart` installed

- [ ] **Step 2: Write the failing tests**

Create `tests/test_cv_import_api.py`:

```python
"""POST /api/cv/import: multipart PDF/DOCX → reviewable master_cv.draft.yaml (F2 wizard)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _redirect_profile_dir(monkeypatch, tmp_path):
    import engine.paths as paths

    monkeypatch.setattr(paths, "MASTER_CV_PATH", tmp_path / "profile" / "master_cv.yaml")


def _docx_bytes(tmp_path) -> bytes:
    from docx import Document

    p = tmp_path / "cv.docx"
    d = Document()
    d.add_paragraph("Jane Ejemplo — Data Engineer")
    d.add_paragraph("Experience: built pipelines at FicticiaCorp.")
    d.save(str(p))
    return p.read_bytes()


def test_import_docx_returns_draft_and_writes_file(atlas_app, tmp_path, monkeypatch):
    _redirect_profile_dir(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        resp = client.post(
            "/api/cv/import",
            files={
                "file": (
                    "cv.docx",
                    _docx_bytes(tmp_path),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True and body["chars"] > 0
    assert "Jane Ejemplo" in body["draft"]          # raw text landed in _source_text
    assert "_source_text" in body["draft"]
    draft_path = tmp_path / "profile" / "master_cv.draft.yaml"
    assert draft_path.exists()
    assert not (tmp_path / "profile" / "master_cv.yaml").exists()  # NEVER writes the real CV


def test_import_rejects_unsupported_format(atlas_app, tmp_path, monkeypatch):
    _redirect_profile_dir(monkeypatch, tmp_path)
    with TestClient(atlas_app) as client:
        resp = client.post(
            "/api/cv/import", files={"file": ("cv.txt", b"plain text", "text/plain")}
        )
    assert resp.status_code == 400


def test_import_rejects_foreign_origin(atlas_app):
    with TestClient(atlas_app) as client:
        resp = client.post(
            "/api/cv/import",
            files={"file": ("cv.docx", b"x", "application/octet-stream")},
            headers={"origin": "https://evil.example.com"},
        )
    assert resp.status_code == 403
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `rtk uv run --group dev pytest tests/test_cv_import_api.py -v`
Expected: FAIL — 404 on `/api/cv/import`

- [ ] **Step 4: Implement the endpoint (`dashboard/backend/main.py`)**

4a. Extend the fastapi import (line 17):

```python
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, UploadFile
```

4b. Add after `api_cv_library`:

```python
@app.post("/api/cv/import", dependencies=[Depends(require_trusted_origin)])
async def api_cv_import(file: UploadFile):
    """Extract an uploaded CV (PDF/DOCX) into a reviewable master_cv DRAFT (F2 wizard).

    Deterministic text extraction only (engine/cv/import_cv.py) — never invents structure
    and NEVER touches master_cv.yaml; the human + Cowork map the draft afterwards. The
    upload and the draft live only in the profile's gitignored dirs (repo is public).
    """
    from engine.cv.import_cv import SUPPORTED, build_draft, extract_text

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(
            400, f"formato no soportado {suffix!r}; usa PDF o DOCX"
        )
    paths.ensure_dirs()
    dest = paths.INBOX_DIR / f"cv_import{suffix}"
    dest.write_bytes(await file.read())
    try:
        text = extract_text(dest)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if not text.strip():
        raise HTTPException(
            400, "no se pudo extraer texto (¿PDF escaneado/solo imagen?) — prueba otro archivo"
        )
    draft = build_draft(text, domain=profiles.domain_of(paths.PROFILE_ID))
    draft_path = paths.MASTER_CV_PATH.parent / "master_cv.draft.yaml"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(draft)
    return {"ok": True, "draft": draft, "path": str(draft_path), "chars": len(text)}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `rtk uv run --group dev pytest tests/test_cv_import_api.py tests/test_import_cv.py -v`
Expected: all pass

- [ ] **Step 6: Lint + commit**

```bash
rtk uv run ruff check dashboard/backend/main.py tests/test_cv_import_api.py && rtk uv run ruff format dashboard/backend/main.py tests/test_cv_import_api.py
rtk git add pyproject.toml uv.lock dashboard/backend/main.py tests/test_cv_import_api.py
rtk git commit -m "feat(onboarding): POST /api/cv/import — multipart CV upload to reviewable draft

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: Frontend data layer + geo/repost badges (card + detail)

**Files:**
- Modify: `dashboard/frontend/src/api.ts` (Job type ~line 35; helpers after `post` ~line 188; api entries at the end of the object)
- Create: `dashboard/frontend/src/components/JobBadges.tsx`
- Test: `dashboard/frontend/src/components/JobBadges.test.tsx`
- Modify: `dashboard/frontend/src/components/Board.tsx` (JobCard meta row, after the knockout icon span ~line 116)
- Modify: the job-detail header chip row — locate with `rtk grep -rln "knockout_flags" dashboard/frontend/src` (pre-F1: `DetailDrawer.tsx` ~line 607, next to the `Remoto` badge; post-F1: the `/jobs/:id` page)

**Interfaces:**
- Consumes: backend fields `geo_restriction` / `geo_scope` / `repost_count` (flow automatically through `SELECT *` + `analytics.annotate`), endpoints from Tasks 9/12/13.
- Produces (used by Task 15):
  - `api.criteria(): Promise<{ criteria: CriteriaConfig; prose: string }>`
  - `api.saveCriteria(criteria: CriteriaConfig, prose: string)`
  - `api.importCv(file: File): Promise<{ ok: boolean; draft: string; path: string; chars: number }>`
  - `api.livenessSweep()`
  - `GeoBadge({ job })` / `RepostBadge({ job })` components.

- [ ] **Step 1: Write the failing component tests**

Create `dashboard/frontend/src/components/JobBadges.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Job } from "../api";
import { GeoBadge, RepostBadge } from "./JobBadges";

const base: Job = { id: "j1", title: "DE", company: "Acme", state: "shortlisted" };

describe("GeoBadge", () => {
  it("shows the first scope token for a restricted remote job", () => {
    render(<GeoBadge job={{ ...base, geo_scope: "us", geo_restriction: "Remote — US only" }} />);
    expect(screen.getByText("us")).toBeInTheDocument();
    expect(screen.getByTitle(/Remote — US only/)).toBeInTheDocument();
  });

  it("renders nothing for worldwide / unknown / empty scopes", () => {
    const { container } = render(
      <>
        <GeoBadge job={{ ...base, geo_scope: "worldwide" }} />
        <GeoBadge job={{ ...base, geo_scope: "unknown" }} />
        <GeoBadge job={base} />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("RepostBadge", () => {
  it("shows a repost chip when repost_count ≥ 1", () => {
    render(<RepostBadge job={{ ...base, repost_count: 2 }} />);
    expect(screen.getByText("repost")).toBeInTheDocument();
    expect(screen.getByTitle(/2/)).toBeInTheDocument();
  });

  it("renders nothing at repost_count 0 or undefined", () => {
    const { container } = render(
      <>
        <RepostBadge job={{ ...base, repost_count: 0 }} />
        <RepostBadge job={base} />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix dashboard/frontend test`
Expected: FAIL — `Cannot find module './JobBadges'`

- [ ] **Step 3: Implement**

3a. `dashboard/frontend/src/api.ts` — extend the `Job` type (after `jd_skills`):

```ts
  // F2 geo-scoring + hygiene (additive; backend may omit on older rows)
  geo_restriction?: string | null; // raw restriction text ("Remote — US only")
  geo_scope?: string | null; // normalized: iso2/region tokens | "worldwide" | "unknown" | ""
  repost_count?: number | null; // ≥1 = same company re-posted this role in 90 days
```

3b. Add the `CriteriaConfig` type (next to `OnboardingStatus`):

```ts
// Frontmatter of the active profile's criteria.md (GET/PUT /api/criteria). Only the fields
// the wizard edits are typed; everything else round-trips untouched via the index signature.
export type CriteriaConfig = {
  roles: string[];
  role_aliases: string[];
  seniority: string[];
  remote_required: boolean;
  onsite_locations: string[];
  languages: string[];
  salary_floor_usd: number;
  candidate_years: number;
  candidate_country: string;
  acceptable_regions: string[];
  geo_penalty: number;
  re_apply_window_days: number;
  shortlist_threshold: number;
  [key: string]: unknown;
};
```

3c. Add the helpers after `post` (line 188):

```ts
async function put<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}
async function postForm<T>(url: string, form: FormData): Promise<T> {
  const r = await fetch(url, { method: "POST", body: form });
  if (!r.ok) throw new Error(`${url} → ${r.status}`);
  return r.json();
}
```

3d. Add the api entries (before `exportUrl`):

```ts
  // F2: onboarding wizard + hygiene
  criteria: () => get<{ criteria: CriteriaConfig; prose: string }>("/api/criteria"),
  saveCriteria: (criteria: CriteriaConfig, prose: string) =>
    put<{ ok: boolean; path: string }>("/api/criteria", { criteria, prose }),
  importCv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return postForm<{ ok: boolean; draft: string; path: string; chars: number }>(
      "/api/cv/import",
      form,
    );
  },
  livenessSweep: () => post<{ started: boolean; running?: boolean }>("/api/liveness/sweep"),
```

3e. Create `dashboard/frontend/src/components/JobBadges.tsx`:

```tsx
import { Globe, Repeat } from "lucide-react";
import type { Job } from "../api";
import { Badge } from "./ui/badge";

// Scopes that mean "no restriction" — the geo chip only appears on a real restriction.
const OPEN_SCOPES = ["", "worldwide", "unknown"];

/** Chip for a remote job restricted to a country/region ("Remote — US only"). */
export function GeoBadge({ job }: { job: Job }) {
  const scope = (job.geo_scope || "").trim();
  if (!scope || OPEN_SCOPES.includes(scope)) return null;
  return (
    <Badge
      variant="warning"
      className="px-1.5 py-0 text-[0.62rem] uppercase"
      title={`Remoto con restricción geográfica: ${job.geo_restriction || scope.toUpperCase()}`}
    >
      <Globe className="size-3" /> {scope.split(",")[0]}
    </Badge>
  );
}

/** Chip for a posting the same company re-published ≥2× in 90 días (posible ghost job). */
export function RepostBadge({ job }: { job: Job }) {
  const n = job.repost_count ?? 0;
  if (n < 1) return null;
  return (
    <Badge
      variant="secondary"
      className="px-1.5 py-0 text-[0.62rem]"
      title={`Republicado ${n} ${n === 1 ? "vez" : "veces"} en 90 días — posible ghost job`}
    >
      <Repeat className="size-3" /> repost
    </Badge>
  );
}
```

3f. `dashboard/frontend/src/components/Board.tsx` — add the import:

```tsx
import { GeoBadge, RepostBadge } from "./JobBadges";
```

…and inside `JobCard`'s meta row, right after the knockout icon `</span>` (line 116) and before the `sources` span:

```tsx
        <GeoBadge job={job} />
        <RepostBadge job={job} />
```

3g. Job detail header — run `rtk grep -rln "knockout_flags" dashboard/frontend/src` to find the detail component (post-F1 the `/jobs/:id` page; pre-F1 `DetailDrawer.tsx`). In its header chip row (pre-F1: right after `{d.job.is_remote === 1 && <Badge variant="secondary">Remoto</Badge>}`, line 607), add the same two components with the file's job variable:

```tsx
                <GeoBadge job={d.job} />
                <RepostBadge job={d.job} />
```

…and the import at the top of that file:

```tsx
import { GeoBadge, RepostBadge } from "./JobBadges";
```

(adjust the relative path if F1 moved the detail out of `components/`).

- [ ] **Step 4: Run tests + typecheck to verify they pass**

Run: `npm --prefix dashboard/frontend test && npm --prefix dashboard/frontend run typecheck`
Expected: all Vitest suites pass; tsc clean

- [ ] **Step 5: Format + commit**

```bash
npm --prefix dashboard/frontend run format
rtk git add dashboard/frontend/src/api.ts dashboard/frontend/src/components/JobBadges.tsx dashboard/frontend/src/components/JobBadges.test.tsx dashboard/frontend/src/components/Board.tsx dashboard/frontend/src/components/DetailDrawer.tsx
rtk git commit -m "feat(ui): geo-restriction + repost badges on kanban card and job detail

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(If the detail lives in another file post-F1, `git add` that file instead of `DetailDrawer.tsx`.)

---

### Task 15: OnboardingWizard (multi-step, replaces OnboardingGate)

**Files:**
- Create: `dashboard/frontend/src/components/onboarding/OnboardingWizard.tsx`
- Test: `dashboard/frontend/src/components/onboarding/OnboardingWizard.test.tsx`
- Modify: the component that renders `<OnboardingGate` — locate with `rtk grep -rln "OnboardingGate" dashboard/frontend/src` (post-F1: the `/onboarding` route module; pre-F1: `App.tsx`)
- Delete: `dashboard/frontend/src/components/OnboardingGate.tsx`

**Interfaces:**
- Consumes: `api.criteria` / `api.saveCriteria` / `api.importCv` (Task 14), `api.profiles` / `api.renameProfile` / `api.completeOnboarding` / `api.cvAudit` (existing), `OnboardingStatus` (existing), `ui/` primitives.
- Produces: `OnboardingWizard({ status, onDone }: { status: OnboardingStatus; onDone: () => void })` — on finish it PUTs criteria, renames the profile, marks onboarding complete and calls `onDone()`.

- [ ] **Step 1: Write the failing test**

Create `dashboard/frontend/src/components/onboarding/OnboardingWizard.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { OnboardingStatus } from "../../api";

vi.mock("../../api", () => ({
  api: {
    criteria: vi.fn().mockResolvedValue({
      criteria: {
        roles: ["data engineer"],
        role_aliases: [],
        seniority: ["senior"],
        remote_required: true,
        onsite_locations: [],
        languages: ["en", "es"],
        salary_floor_usd: 0,
        candidate_years: 0,
        candidate_country: "",
        acceptable_regions: ["worldwide"],
        geo_penalty: 12,
        re_apply_window_days: 0,
        shortlist_threshold: 60,
      },
      prose: "",
    }),
    profiles: vi.fn().mockResolvedValue({
      active: "owner",
      profiles: [{ id: "owner", label: "Jane Ejemplo" }],
    }),
    saveCriteria: vi.fn().mockResolvedValue({ ok: true, path: "/tmp/criteria.md" }),
    renameProfile: vi.fn().mockResolvedValue({ ok: true, id: "owner", label: "Jane Ejemplo" }),
    completeOnboarding: vi.fn().mockResolvedValue({ ok: true }),
    importCv: vi.fn().mockResolvedValue({ ok: true, draft: "basics:", path: "x", chars: 10 }),
    cvAudit: vi.fn().mockResolvedValue({
      cv_present: false,
      audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
    }),
  },
}));

import { api } from "../../api";
import { OnboardingWizard } from "./OnboardingWizard";

const status: OnboardingStatus = {
  complete: false,
  profile: "owner",
  domain: "data",
  target_label: "",
  cv_present: false,
  audit: { findings: [], summary: { high: 0, med: 0, low: 0 } },
};

async function renderWizard(onDone = vi.fn()) {
  render(<OnboardingWizard status={status} onDone={onDone} />);
  await screen.findByText("Tu perfil"); // step 1 heading appears once criteria loaded
  return onDone;
}

describe("OnboardingWizard", () => {
  it("navigates: country step comes after identity", async () => {
    await renderWizard();
    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    expect(await screen.findByText("País y regiones")).toBeInTheDocument();
  });

  it("saves criteria (with the typed country) and completes onboarding on finish", async () => {
    const onDone = await renderWizard();
    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ })); // → geo
    await userEvent.type(screen.getByLabelText(/País de residencia/), "ec");
    for (let i = 0; i < 4; i++) {
      await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
    }
    await userEvent.click(screen.getByRole("button", { name: /Finalizar/ }));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(api.saveCriteria).toHaveBeenCalledWith(
      expect.objectContaining({ candidate_country: "ec" }),
      expect.any(String),
    );
    expect(api.completeOnboarding).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix dashboard/frontend test`
Expected: FAIL — `Cannot find module './OnboardingWizard'`

- [ ] **Step 3: Implement `dashboard/frontend/src/components/onboarding/OnboardingWizard.tsx`**

```tsx
import { ArrowLeft, ArrowRight, Check, FileUp, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type CriteriaConfig, type OnboardingStatus } from "../../api";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";

const REGION_OPTIONS = [
  { id: "worldwide", label: "Mundial (remotos sin restricción)" },
  { id: "latam", label: "Latinoamérica" },
  { id: "na", label: "Norteamérica" },
  { id: "eu", label: "Europa" },
  { id: "apac", label: "Asia-Pacífico" },
];
const LANGUAGE_OPTIONS = ["en", "es", "de", "fr", "pt"];
const STEPS = [
  "Tu perfil",
  "País y regiones",
  "Tipo de trabajo",
  "Salario e idiomas",
  "Tu CV",
  "Fuentes iniciales",
];

const listToText = (xs: string[] | undefined): string => (xs || []).join(", ");
const textToList = (s: string): string[] =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

// F2: per-profile onboarding wizard (replaces OnboardingGate). Everything configurable —
// nothing hardcoded per candidate. Writes criteria.md via PUT /api/criteria on finish.
export function OnboardingWizard({
  status,
  onDone,
}: {
  status: OnboardingStatus;
  onDone: () => void;
}) {
  const [step, setStep] = useState(0);
  const [criteria, setCriteria] = useState<CriteriaConfig | null>(null);
  const [prose, setProse] = useState("");
  const [label, setLabel] = useState("");
  const [rolesText, setRolesText] = useState("");
  const [onsiteText, setOnsiteText] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.criteria().then((r) => {
      setCriteria(r.criteria);
      setProse(r.prose);
      setRolesText(listToText(r.criteria.roles));
      setOnsiteText(listToText(r.criteria.onsite_locations));
    });
    api.profiles().then((p) => {
      setLabel(p.profiles.find((x) => x.id === p.active)?.label || "");
    });
  }, []);

  if (!criteria) {
    return (
      <div className="py-16 text-center text-sm text-muted-foreground">Cargando tu perfil…</div>
    );
  }

  const set = (patch: Partial<CriteriaConfig>) => setCriteria({ ...criteria, ...patch });
  const toggleIn = (key: "acceptable_regions" | "languages", value: string) => {
    const xs = (criteria[key] as string[]) || [];
    set({ [key]: xs.includes(value) ? xs.filter((x) => x !== value) : [...xs, value] });
  };

  async function importFile(file: File) {
    setImporting(true);
    try {
      const r = await api.importCv(file);
      setDraft(r.draft);
      toast.success("CV importado — borrador creado para tu revisión");
    } catch {
      toast.error("No se pudo importar el CV (usa PDF o DOCX con texto)");
    } finally {
      setImporting(false);
    }
  }

  async function finish() {
    setSaving(true);
    try {
      await api.saveCriteria(
        { ...criteria, roles: textToList(rolesText), onsite_locations: textToList(onsiteText) },
        prose,
      );
      if (label.trim()) await api.renameProfile(status.profile, label.trim());
      await api.completeOnboarding();
      toast.success("Perfil configurado — ¡a buscar!");
      onDone();
    } catch {
      toast.error("No se pudo guardar la configuración");
    } finally {
      setSaving(false);
    }
  }

  const last = step === STEPS.length - 1;

  return (
    <div className="fade-up mx-auto max-w-[720px] py-8">
      {/* progress */}
      <div className="mb-6 flex items-center justify-center gap-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={
                "grid size-6 place-items-center rounded-full text-[0.7rem] font-semibold " +
                (i < step
                  ? "bg-primary text-primary-foreground"
                  : i === step
                    ? "bg-secondary text-foreground ring-1 ring-primary"
                    : "bg-secondary text-muted-foreground")
              }
              title={s}
            >
              {i < step ? <Check className="size-3.5" /> : i + 1}
            </div>
            {i < STEPS.length - 1 && <div className="h-px w-6 bg-border" />}
          </div>
        ))}
      </div>

      <Card className="p-6">
        <h1 className="mb-1 text-lg font-semibold">{STEPS[step]}</h1>

        {step === 0 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Cómo te llamas y en qué industria buscas. El dominio define el vocabulario del
              motor (roles, seniority, CV) y viene del pack elegido al crear el perfil.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-label">Nombre del perfil</Label>
              <Input
                id="wiz-label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Tu nombre"
              />
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Dominio:</span>
              <Badge variant="secondary">{status.domain || "data"}</Badge>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Muchos remotos exigen residir en un país/región. Con tu país, Atlas penaliza
              (sin ocultar) los que no te aplican — p. ej. “Remote — US only”.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-country">País de residencia (código ISO-2)</Label>
              <Input
                id="wiz-country"
                className="max-w-[160px] font-mono lowercase"
                value={criteria.candidate_country}
                onChange={(e) => set({ candidate_country: e.target.value.trim().toLowerCase() })}
                placeholder="ec, mx, es…"
                maxLength={2}
              />
              <p className="text-[0.75rem] text-muted-foreground">
                Vacío = sin penalización geográfica.
              </p>
            </div>
            <div className="space-y-2">
              <Label>Regiones que también te sirven</Label>
              {REGION_OPTIONS.map((r) => (
                <Label key={r.id} className="flex cursor-pointer items-center gap-2 font-normal">
                  <Checkbox
                    checked={(criteria.acceptable_regions || []).includes(r.id)}
                    onCheckedChange={() => toggleIn("acceptable_regions", r.id)}
                  />
                  {r.label}
                </Label>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="wiz-roles">Roles objetivo (separados por coma)</Label>
              <Input
                id="wiz-roles"
                value={rolesText}
                onChange={(e) => setRolesText(e.target.value)}
                placeholder="data engineer, analytics engineer"
              />
            </div>
            <Label className="flex cursor-pointer items-center gap-2 font-normal">
              <Switch
                checked={criteria.remote_required}
                onCheckedChange={(v) => set({ remote_required: Boolean(v) })}
              />
              Solo trabajos 100% remotos
            </Label>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-onsite">Ubicaciones aceptables para presencial (coma)</Label>
              <Input
                id="wiz-onsite"
                value={onsiteText}
                onChange={(e) => setOnsiteText(e.target.value)}
                placeholder="quito, guayaquil, , ec"
              />
              <p className="text-[0.75rem] text-muted-foreground">
                Vacío = sin filtro presencial. Los remotos nunca se filtran por esto.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-years">Años de experiencia reales</Label>
              <Input
                id="wiz-years"
                type="number"
                min={0}
                className="max-w-[120px]"
                value={criteria.candidate_years || 0}
                onChange={(e) => set({ candidate_years: Number(e.target.value) || 0 })}
              />
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="wiz-salary">Salario mínimo anual (USD, 0 = sin piso)</Label>
              <Input
                id="wiz-salary"
                type="number"
                min={0}
                className="max-w-[180px]"
                value={criteria.salary_floor_usd || 0}
                onChange={(e) => set({ salary_floor_usd: Number(e.target.value) || 0 })}
              />
            </div>
            <div className="space-y-2">
              <Label>Idiomas en los que aceptas ofertas</Label>
              <div className="flex flex-wrap gap-3">
                {LANGUAGE_OPTIONS.map((l) => (
                  <Label key={l} className="flex cursor-pointer items-center gap-1.5 font-normal">
                    <Checkbox
                      checked={(criteria.languages || []).includes(l)}
                      onCheckedChange={() => toggleIn("languages", l)}
                    />
                    <span className="uppercase">{l}</span>
                  </Label>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Sube tu CV (PDF/DOCX). Atlas extrae el texto a un <b>borrador revisable</b> (
              <code className="font-mono">master_cv.draft.yaml</code>) — nunca escribe tu{" "}
              <code className="font-mono">master_cv.yaml</code> directo: lo mapeás y confirmás
              vos (con ayuda de Claude si querés).
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])}
            />
            <Button
              variant="secondary"
              disabled={importing}
              onClick={() => fileRef.current?.click()}
            >
              {importing ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileUp className="size-4" />
              )}
              {importing ? "Importando…" : "Subir CV (PDF/DOCX)"}
            </Button>
            {status.cv_present && !draft && (
              <p className="text-sm text-success">
                Ya tienes un master_cv.yaml — puedes saltar este paso.
              </p>
            )}
            {draft && (
              <Card className="max-h-56 overflow-auto p-3">
                <pre className="font-mono text-[0.7rem] whitespace-pre-wrap">{draft}</pre>
              </Card>
            )}
          </div>
        )}

        {step === 5 && (
          <div className="space-y-4 text-sm">
            <p className="text-muted-foreground">
              (Opcional) Las empresas que Atlas vigila directamente viven en{" "}
              <code className="font-mono">profiles/{status.profile}/config/companies.yaml</code>.
              Puedes editarlas ahora o después desde Ajustes; añadir empresas por URL llega en la
              Fase 3. Las fuentes públicas (job boards) ya vienen activas.
            </p>
            <p className="text-muted-foreground">
              Al finalizar se guardan tus criterios y se desbloquea el tablero.
            </p>
          </div>
        )}

        {/* footer nav */}
        <div className="mt-6 flex items-center justify-between">
          <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
            <ArrowLeft className="size-4" /> Atrás
          </Button>
          {!last ? (
            <Button onClick={() => setStep(step + 1)}>
              Siguiente <ArrowRight className="size-4" />
            </Button>
          ) : (
            <Button disabled={saving} onClick={finish}>
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
              Finalizar
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Run the wizard test**

Run: `npm --prefix dashboard/frontend test`
Expected: OnboardingWizard tests pass (other suites still green)

- [ ] **Step 5: Mount it and remove OnboardingGate**

Run `rtk grep -rln "OnboardingGate" dashboard/frontend/src` — edit the render site (post-F1 the `/onboarding` route module; pre-F1 `App.tsx`):

- Replace the import:

```tsx
import { OnboardingWizard } from "./components/onboarding/OnboardingWizard";
```

- Replace the render (pre-F1 `App.tsx` passes `status`, `onComplete`, `onRefresh` — the wizard only needs the first two):

```tsx
<OnboardingWizard status={onboardingStatus} onDone={handleOnboardingComplete} />
```

(use the file's actual variable names for the status object and the completion callback — they are the same props previously passed as `status` and `onComplete`).

- Delete the old component:

```bash
rtk git rm dashboard/frontend/src/components/OnboardingGate.tsx
```

- [ ] **Step 6: Full frontend gate**

Run: `npm --prefix dashboard/frontend test && npm --prefix dashboard/frontend run typecheck && npm --prefix dashboard/frontend run build`
Expected: tests green, tsc clean, build succeeds

- [ ] **Step 7: Format + commit**

```bash
npm --prefix dashboard/frontend run format
rtk git add dashboard/frontend/src/components/onboarding/OnboardingWizard.tsx dashboard/frontend/src/components/onboarding/OnboardingWizard.test.tsx dashboard/frontend/src/App.tsx
rtk git commit -m "feat(onboarding): multi-step per-profile wizard replaces OnboardingGate

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(If the mount lives in another file post-F1, `git add` that file instead of `App.tsx`; the `git rm` above already staged the deletion.)

---

### Task 16: Final gate — full suites + repo check

**Files:** none (verification only).

**Interfaces:** none.

- [ ] **Step 1: Full backend suite**

Run: `rtk uv run --group dev pytest`
Expected: ALL tests pass (117 pre-existing + the ~45 added in this plan), 0 failures

- [ ] **Step 2: Full frontend suite + build**

Run: `npm --prefix dashboard/frontend test && npm --prefix dashboard/frontend run build`
Expected: all Vitest suites pass; `vite build` completes

- [ ] **Step 3: Repo health check**

Run: `./scripts/check.sh`
Expected: `✓ All checks passed.`

- [ ] **Step 4: Confirm no personal data staged**

Run: `rtk git status && rtk git log --stat -1`
Expected: no files under `profiles/`, `config/criteria.md`, `config/companies.yaml` or `data/` in any commit of this branch (only `.example`/seed files were touched).

- [ ] **Step 5: Close the branch**

Do NOT merge or push on your own initiative. Use the `superpowers:finishing-a-development-branch` skill: verify tests, then present the merge / PR / keep / discard menu — the merge decision belongs to the user (personal repo, master protected: open a PR for this phase).

---

## Self-Review (done at plan-writing time)

- **Spec §5 coverage:** 5.1 wizard (T12, T13, T15), 5.2 extraction+fields+criteria+factor 2c+badges (T1–T5, T14), 5.3 liveness (T8, T9), reposts (T7), geo-mismatch (T6), re-apply window (T10), posting archive (T11). §8 geo corpus is verbatim in T2. Gate per §8 in T16. ✓
- **Placeholders:** none — every step carries code or an exact command. The two F1-dependent edit sites (detail header, wizard mount) carry an exact locator command + the exact snippet. ✓
- **Type consistency:** `extract_geo_restriction(location, description, is_remote) -> tuple[str | None, str]` used identically in T2/T3; `geo_scope_covers(scope, country, regions)` in T1/T5; `sweep_liveness(db, *, limit, client, delay_s) -> dict` in T8/T9; `CriteriaConfig`/`api.saveCriteria(criteria, prose)` in T14/T15; knockout string prefixes (`"remoto restringido a "`, `'dice remoto pero: "'`, `"repost ("`, `"aplicaste a esta empresa hace "`) consistent across producer tasks and their tests. ✓
