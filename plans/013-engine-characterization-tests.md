# Plan 013: Characterization & behavioral tests for the engine critical paths

> **Status: PARTIALLY IMPLEMENTED.** Some of the coverage this finding called for
> already landed via other plans (002/003/004/006/011) — see "What is already
> covered" below. This file tracks the **remaining** test coverage to add. Write
> the new work as future work; do not re-add what already exists.
>
> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat c3e2679..HEAD -- tests/ engine/discovery/ats/ engine/outreach/templates.py dashboard/backend/main.py engine/analytics.py`
> If any cited file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/003-*.md, plans/006-*.md (both add inline tests this plan builds beside; land them first to avoid file-level merge churn in `tests/`)
- **Category**: tests
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

Six discovery parsers (greenhouse, lever, ashby, smartrecruiters, himalayas,
adzuna), the analytics read paths (`overview`, `needs_action`), the FastAPI
mutation routes, and the outreach length caps are the engine's load-bearing
edges — they map untrusted external JSON into the `Job` model and mutate the
DB — yet they have **zero direct tests**. A silent change to a parser's field
mapping (e.g. a vendor renames `workplaceType`, or a salary `interval` format
shifts) would pass CI today and quietly corrupt remote/salary filtering. This
plan adds **characterization tests**: they lock the *current observed* behavior
(not an idealized spec) using saved JSON fixtures fed through a stub HTTP
client, so any future drift in the mapping or the caps fails loudly and
network-free.

## What is already covered (do NOT re-add)

Other plans added inline tests for these; leave them alone:

- Lever `salary_interval` `per-` stripping (plan 002).
- Discovery `--only <source>` routing (plan 003).
- The CV-download path guard (plan 004).
- Follow-up cadence / reply-aware follow-ups (plan 006).
- `db.list_jobs(...)` generators and `analytics` counts (plan 011).

This plan adds the **remaining** gaps: fixture-based parser mapping tests, a
FastAPI `TestClient` module for the mutation routes, and outreach template cap
boundary tests.

## Current state

Files involved (role, one line each):

- `tests/test_engine.py` — the existing (and only) test module; 121 lines.
  Network-free unit tests. Use its fixture + `CRITERIA` constant as the
  structural pattern. New tests go in **new** sibling modules, not here.
- `engine/discovery/ats/greenhouse.py` — `fetch(target, client)` maps the
  Greenhouse board JSON → `list[Job]`.
- `engine/discovery/ats/lever.py` — `fetch(target, client)` maps Lever postings
  JSON → `list[Job]`, deriving `workplace_type`/`is_remote`/salary.
- `engine/discovery/ats/smartrecruiters.py` — `fetch(target, client)`; two-tier
  list+detail, `is_remote` from `location.remote`.
- `engine/discovery/http.py` — `get_json(client, url, params=, retries=)`; the
  seam every parser goes through. A stub `client` with a `.get(url, params=)`
  returning an object exposing `status_code`, `headers`, `raise_for_status()`,
  `json()` is sufficient to drive parsers without a network.
- `engine/outreach/templates.py` — the length caps under test.
- `dashboard/backend/main.py` — FastAPI app `app` and the mutation routes.
- `engine/analytics.py` — `overview(db)`, `needs_action(db)`, `job_detail(db, job_id)`.
- `engine/paths.py` — `DB_PATH = DATA_DIR / "atlas.db"`, where
  `DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", REPO_ROOT / "data"))`.

### Exact code to characterize

Existing test fixture + criteria pattern to copy — `tests/test_engine.py:6-27`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from engine.config import Criteria
from engine.db.models import DB
from engine.normalize import Job, compute_job_id


@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")


CRITERIA = Criteria(
    roles=["data scientist", "ai engineer"], role_aliases=["data specialist"],
    remote_required=True, salary_floor_usd=70000, salary_hard=False,
    must_haves=["sql", "python"], deal_breakers=["on-site only", "internship"],
    knockout_terms=["security clearance"], shortlist_threshold=62,
)
```

The HTTP seam — `engine/discovery/http.py:31-44` (parsers call this; stub the
`client` so this returns parsed JSON without a network):

```python
def get_json(client: httpx.Client, url: str, params: Optional[dict] = None,
             retries: int = 2) -> Any:
    """GET a URL and parse JSON, backing off briefly on 429. Raises on other HTTP errors."""
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            r = client.get(url, params=params)
            if r.status_code == 429:
                ...
            r.raise_for_status()
            return r.json()
```

Lever mapping — `engine/discovery/ats/lever.py:24-49` (the remote/salary logic
to lock):

```python
    for p in data if isinstance(data, list) else []:
        cats = p.get("categories") or {}
        sal = p.get("salaryRange") or {}
        wt = (p.get("workplaceType") or "").lower()  # remote | on-site | hybrid
        location = first(cats.get("location"), cats.get("allLocations"))
        if isinstance(location, list):
            location = ", ".join(location)
        jobs.append(Job(
            source="lever",
            source_job_id=p.get("id"),
            ...
            workplace_type=wt or "unknown",
            is_remote=True if wt == "remote" else (False if wt in ("on-site", "hybrid") else None),
            ...
            salary_interval=(sal.get("interval") or "").replace("per-", "") or None,
            ...
        ))
```

Greenhouse mapping — `engine/discovery/ats/greenhouse.py:18-36`:

```python
def fetch(target: CompanyTarget, client: httpx.Client) -> list[Job]:
    url = f"{BASE}/{target.token}/jobs"
    data = get_json(client, url, params={"content": "true"})
    jobs: list[Job] = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name")
        jobs.append(Job(
            source="greenhouse",
            source_job_id=str(j.get("id")),
            title=j.get("title", "").strip(),
            ...
            description=html_to_text(j.get("content")),
            date_posted=(j.get("updated_at") or "")[:10] or None,
        ))
```

SmartRecruiters mapping — `engine/discovery/ats/smartrecruiters.py:19-24, 37-56`
(note `DETAIL_CAP = 40` bounds the N+1 detail fetch, and `is_remote` is
tri-state):

```python
def _location_str(loc: dict) -> str:
    parts = [loc.get("city"), loc.get("region"), loc.get("country")]
    s = ", ".join(p for p in parts if p)
    if loc.get("remote"):
        s = (s + " (Remote)").strip()
    return s
...
    for i, p in enumerate(listing.get("content", [])):
        loc = p.get("location") or {}
        ...
        is_remote=bool(loc.get("remote")) if "remote" in loc else None,
```

Outreach caps — `engine/outreach/templates.py:31-33`:

```python
def _word_cap(text: str, max_words: int = 125) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]).rstrip(",.;") + "…"
```

`engine/outreach/templates.py:52-58`:

```python
def _skills_phrase(matched: list[str], n: int = 3) -> str:
    top = [_pretty(s) for s in matched[:n]]
    if not top:
        return "data science and analytics"
    if len(top) == 1:
        return top[0]
    return ", ".join(top[:-1]) + f" and {top[-1]}"
```

`engine/outreach/templates.py:173-181`:

```python
def _linkedin_note(company: str, role: str, language: str) -> str:
    """120–180 char connection note — a reason to accept, no pitch."""
    if language == "es":
        note = f"Hola, sigo a {company} y vi la vacante de {role}. ..."
    else:
        note = f"Hi — I follow {company} and saw the {role} opening. ..."
    if len(note) > 180:
        note = note[:177].rstrip() + "…"
    return note
```

FastAPI mutation routes — `dashboard/backend/main.py:68-105`:

```python
@app.post("/api/jobs/{job_id}/state")
def api_set_state(job_id: str, body: StateBody):
    if body.state not in STATES:
        raise HTTPException(400, f"invalid state; must be one of {STATES}")
    with DB() as db:
        if not db.get_job(job_id):
            raise HTTPException(404, "job not found")
        db.set_state(job_id, body.state, {"via": "dashboard"})
    return {"ok": True, "state": body.state}

@app.post("/api/jobs/{job_id}/applied")
def api_mark_applied(job_id: str):
    with DB() as db:
        db.set_state(job_id, "applied", {"via": "dashboard"})  # NOTE: no 404 guard here
    return {"ok": True}

@app.post("/api/messages/{message_id}/sent")
def api_mark_sent(message_id: int):
    with DB() as db:
        db.conn.execute("UPDATE messages SET state='sent', sent_at=? WHERE id=?",
                        (now_iso(), message_id))
        db.conn.commit()
    return {"ok": True}
```

The `StateBody` model is at `dashboard/backend/main.py:29-30`:
`class StateBody(BaseModel): state: str`. `STATES` is the 12-value list in
`engine/normalize.py:12-25`.

### Conventions this plan MUST match (lifted from the codebase)

- `from __future__ import annotations` at the top of every new module.
- typer CLI + pydantic v2 models + rich.console elsewhere (not exercised here,
  but do not break imports).
- DB tests use a per-test temp file via the `db` fixture
  (`DB(tmp_path / "test.db")`) — sqlite3 PARAMETERIZED queries + WAL, idempotent
  UPSERT + COALESCE gap-fill (already enforced by `DB`; just instantiate it).
- `@dataclass` for result objects elsewhere; tests assert on `Job` (pydantic)
  attributes directly.
- New tests model after `tests/test_engine.py` — same fixture style, plain
  `assert`, no test classes.
- Network-free is mandatory. Parsers receive a **stub** client; the backend
  receives a temp DB via `ATLAS_DATA_DIR`. No real HTTP, no real `data/atlas.db`.

### Load-bearing path detail for the backend tests

`engine/db/models.py:19` binds `DB_PATH` **at import time**:
`from engine.paths import DB_PATH, ensure_dirs`, and `DB.__init__` defaults to
that bound value. Therefore `os.environ["ATLAS_DATA_DIR"]` must be set **before**
`engine.paths` / `engine.db.models` / `dashboard.backend.main` are first
imported in the test process, or the routes will hit the real `data/atlas.db`.
Set it in a `conftest.py` (executed before test-module imports) or via an
autouse session fixture that sets the env var and then imports the app lazily
inside the test. The plan uses the conftest approach (Step 4) — it is the only
reliable way given the import-time binding.

## Commands you will need

| Purpose            | Command                                                | Expected on success                          |
|--------------------|--------------------------------------------------------|----------------------------------------------|
| Python tests (all) | `uv run --extra dev pytest`                            | exit 0; was "9 passed", now "9 + N passed"   |
| Single new module  | `uv run --extra dev pytest tests/test_parsers.py -q`   | all pass                                     |
| Backend module     | `uv run --extra dev pytest tests/test_backend_api.py -q` | all pass                                    |
| Templates module   | `uv run --extra dev pytest tests/test_templates.py -q` | all pass                                     |
| Files changed      | `git status --porcelain`                               | only `tests/` paths listed                   |

> Do NOT use a bare `pytest` — the global interpreter is missing `docx`,
> `rapidfuzz`, and `reportlab` and will falsely fail 2 tests. Always go through
> `uv run --extra dev pytest`.

## Suggested executor toolkit

- FastAPI's `TestClient` ships with Starlette (a transitive dep of
  `fastapi>=0.111`, already in `pyproject.toml`). Import it as
  `from fastapi.testclient import TestClient`. No new dependency is needed; do
  NOT add one.
- `httpx>=0.27` is already a runtime dep — but you do **not** need it for the
  parser tests; a hand-written stub object is simpler and keeps tests offline.

## Scope

**In scope** (the only files you should create/modify):

- `tests/fixtures/` (create the directory + JSON payloads)
- `tests/fixtures/greenhouse_jobs.json` (create)
- `tests/fixtures/lever_postings.json` (create)
- `tests/fixtures/smartrecruiters_postings.json` (create)
- `tests/fixtures/smartrecruiters_detail.json` (create)
- `tests/test_parsers.py` (create)
- `tests/test_backend_api.py` (create)
- `tests/test_templates.py` (create)
- `tests/conftest.py` (create — only if it does not already exist; if it exists,
  STOP and report)
- `plans/README.md` (status row update only)

**Out of scope** (do NOT touch, even though they look related):

- Any file under `engine/` or `dashboard/backend/` — this plan tests behavior,
  it never changes it. If a test reveals a bug (e.g. the missing 404 guard on
  `/applied`), **characterize the current behavior** (assert what it does today)
  and note it in Maintenance — do not fix it here.
- `tests/test_engine.py` — leave the existing module untouched; new tests go in
  new modules.
- The ashby / himalayas / adzuna parsers — covering them is a deferred
  follow-up (see Maintenance). Add them only if Step 2's pattern proves trivial
  to extend AND you have a real saved payload; otherwise leave them.

## Git workflow

- Branch: `advisor/013-engine-characterization-tests` off the latest `main`.
- Commit per logical unit (e.g. one commit for fixtures+parser tests, one for
  backend tests, one for template tests). Match the repo's concise,
  sentence-style messages (see `git log`: e.g. "advisor: surface [confirma] gaps
  in CV audit").
- Stage only the files this session created (`git add tests/... plans/README.md`).
  Never `git add .` / `git add -A`.
- Do NOT push or open a PR. The operator merges to `main` explicitly.

## Steps

### Step 1: Capture fixture payloads (one saved JSON per ATS source)

Create `tests/fixtures/` and write minimal but realistic JSON payloads matching
each vendor's documented shape (from the parser module docstrings). Keep each to
1–2 postings. Cover the discriminating fields each parser reads.

- `greenhouse_jobs.json` — shape `{"jobs": [ {"id":..., "title":..., "location":{"name":...}, "absolute_url":..., "content":"<p>...</p>", "updated_at":"2026-06-01T..."} ]}`. Include one job whose `content` is HTML so `html_to_text` is exercised.
- `lever_postings.json` — a JSON **array** (Lever returns a top-level list) with: one posting `workplaceType="remote"` and a `salaryRange` with `interval="per-year"`; one posting `workplaceType="on-site"`; one with `workplaceType` absent. Include `categories.location` as both a string (one posting) and a list (another) to exercise the `", ".join` branch.
- `smartrecruiters_postings.json` — shape `{"content": [ {"id":..., "name":..., "location":{"city":...,"country":...,"remote":true}, ...} ]}` with one posting whose `location` has `remote: true` and one with no `remote` key (tri-state `None`).
- `smartrecruiters_detail.json` — shape `{"jobAd":{"sections":{"jobDescription":{"text":"<p>...</p>"}}}}` for the detail fetch.

Do not invent fields the parser does not read; keep payloads tight.

**Verify**: `ls tests/fixtures/` → lists the four JSON files; `uv run python -c "import json,glob; [json.load(open(f)) for f in glob.glob('tests/fixtures/*.json')]"` → exit 0 (all valid JSON).

### Step 2: Write `tests/test_parsers.py` — fixture-driven parser mapping tests

Build a tiny offline stub client and feed each parser its fixture, asserting the
mapping the "Current state" excerpts show. Target shape:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.config import CompanyTarget
from engine.discovery.ats import greenhouse, lever, smartrecruiters

FIX = Path(__file__).parent / "fixtures"


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {}
    def raise_for_status(self):  # no-op for 200
        return None
    def json(self):
        return self._payload


class _StubClient:
    """Returns queued payloads in call order; matches get_json's client.get(url, params=)."""
    def __init__(self, *payloads):
        self._queue = list(payloads)
    def get(self, url, params=None):
        return _StubResponse(self._queue.pop(0))


def _load(name):
    return json.loads((FIX / name).read_text())
```

Then, per source (use a `CompanyTarget` — check its required fields with
`uv run python -c "from engine.config import CompanyTarget; print(CompanyTarget.model_fields)"`
before constructing it; `target.token`, `target.company`, and for Lever
`target.eu` are read by the parsers):

- **Greenhouse**: `jobs = greenhouse.fetch(target, _StubClient(_load("greenhouse_jobs.json")))`. Assert `jobs[0].source == "greenhouse"`, `jobs[0].source_job_id` is the stringified id, `jobs[0].description` contains the de-HTML'd text (no `<p>`), and `date_posted` is the 10-char date slice.
- **Lever**: `jobs = lever.fetch(target, _StubClient(_load("lever_postings.json")))`. Assert the remote posting has `is_remote is True` and `workplace_type == "remote"`; the on-site posting has `is_remote is False`; the workplaceType-absent posting has `is_remote is None` and `workplace_type == "unknown"`; the `per-year` salary maps to `salary_interval == "year"`; the list-location posting joins with `", "`.
- **SmartRecruiters**: queue the listing payload then the detail payload: `_StubClient(_load("smartrecruiters_postings.json"), _load("smartrecruiters_detail.json"))`. Assert `is_remote is True` for the `remote:true` posting and `is_remote is None` for the posting with no `remote` key; assert the `url`/`apply_url` follow `https://jobs.smartrecruiters.com/{token}/{pid}`.

**Verify**: `uv run --extra dev pytest tests/test_parsers.py -q` → all pass.

### Step 3: Write `tests/test_templates.py` — outreach cap boundaries

Import the private helpers (they are module-level functions in
`engine/outreach/templates.py`):

```python
from __future__ import annotations

from engine.outreach.templates import _word_cap, _linkedin_note, _skills_phrase
```

Assert the boundaries shown in "Current state":

- `_word_cap`: text with exactly 125 words is returned unchanged (no ellipsis); text with 126 words is truncated to 125 words and ends with `"…"`. Build inputs with `" ".join(["w"] * 125)` and `... * 126`.
- `_linkedin_note`: for both `language="en"` and `language="es"`, with a long `company`/`role` that pushes the note over 180 chars, assert `len(result) <= 180` and it ends with `"…"`; with a short company/role, assert it is returned intact (no ellipsis) and `len(result) <= 180`.
- `_skills_phrase`: empty list → `"data science and analytics"`; single skill → that one pretty-cased skill; three+ skills → Oxford-style `"A, B and C"` form (top `n=3`).

**Verify**: `uv run --extra dev pytest tests/test_templates.py -q` → all pass.

### Step 4: Write `tests/conftest.py` + `tests/test_backend_api.py` — FastAPI TestClient

First, if `tests/conftest.py` already exists, STOP and report (do not overwrite).
Otherwise create it so the data dir is redirected **before** any engine import:

```python
from __future__ import annotations

import os
import pytest


@pytest.fixture
def atlas_app(tmp_path, monkeypatch):
    """Point the backend at a throwaway DB, then import the app fresh."""
    monkeypatch.setenv("ATLAS_DATA_DIR", str(tmp_path))
    # Import lazily AFTER the env var is set so DB_PATH binds to tmp_path.
    import importlib
    import engine.paths, engine.db.models
    importlib.reload(engine.paths)
    importlib.reload(engine.db.models)
    from dashboard.backend import main as backend_main
    importlib.reload(backend_main)
    return backend_main.app
```

If the reload dance proves brittle in this repo (circular import on reload),
STOP and report rather than hacking around it — see STOP conditions. Then:

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from engine.db.models import DB
from engine.normalize import Job


def _seed_job(app) -> str:
    # Use the SAME DB the app uses (ATLAS_DATA_DIR is set by the fixture).
    with DB() as db:
        job = Job(source="greenhouse", source_job_id="1", title="Data Scientist",
                  company="Acme", url="https://x/1")
        jid = db.upsert_job(job)          # confirm the upsert method name first
    return jid
```

> Before writing seeding, confirm the exact `Job` required fields and the
> upsert method name:
> `uv run python -c "from engine.normalize import Job; print(Job.model_fields.keys())"`
> and `uv run python -c "from engine.db.models import DB; print([m for m in dir(DB) if 'job' in m.lower()])"`.
> Match what exists; do not invent method names.

Tests against `TestClient(atlas_app)`:

- **POST `/api/jobs/{id}/state` — invalid state → 400**: body `{"state": "bogus"}` → status 400 (matches the `if body.state not in STATES` guard).
- **POST `/api/jobs/{id}/state` — unknown id → 404**: a valid state on a never-seeded id → status 404 (`if not db.get_job(job_id)`).
- **POST `/api/jobs/{id}/state` — happy path → 200**: seed a job, send a valid state → status 200 and JSON `{"ok": True, "state": <state>}`.
- **POST `/api/jobs/{id}/applied` — characterize current behavior**: per the
  excerpt this route has **no 404 guard**. Assert what it actually does today
  (likely 200 even for an unknown id, since `set_state` runs unconditionally).
  Do NOT change the route — this test documents the current contract.
- **POST `/api/messages/{id}/sent` → 200**: posting to a nonexistent message id
  still returns `{"ok": True}` (the UPDATE matches zero rows). Assert that
  current behavior.

**Verify**: `uv run --extra dev pytest tests/test_backend_api.py -q` → all pass.

### Step 5: Full suite + scope check

**Verify**:
- `uv run --extra dev pytest` → exit 0; pass count went from "9 passed" to "9 + N passed" where N is the number of new test functions added (no failures, no errors).
- `git status --porcelain` → only paths under `tests/` (and `plans/README.md`) appear; nothing under `engine/` or `dashboard/`.

## Test plan

New modules and the cases each covers:

- `tests/test_parsers.py` — greenhouse (source/id/de-HTML/date-slice),
  lever (remote / on-site / unknown tri-state, `per-year`→`year`, list-location
  join), smartrecruiters (remote tri-state, url construction). Happy path +
  the tri-state edge cases that filtering depends on.
- `tests/test_templates.py` — `_word_cap` at the 125/126 boundary,
  `_linkedin_note` ≤180 cap (en + es), `_skills_phrase` empty/single/multi.
- `tests/test_backend_api.py` — `/state` 400 (invalid), 404 (unknown id),
  200 (happy); `/applied` and `/messages/{id}/sent` current-behavior
  characterization.

Structural pattern: model all three after `tests/test_engine.py` (module-level
fixtures, plain `assert`, no test classes).

Verification: `uv run --extra dev pytest` → all pass, including the new tests.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports more than 9 passed (the prior count) with 0 failed / 0 errored.
- [ ] `uv run --extra dev pytest tests/test_parsers.py tests/test_templates.py tests/test_backend_api.py -q` → all pass.
- [ ] `ls tests/fixtures/*.json` lists at least the four created fixtures.
- [ ] `git status --porcelain` shows changes ONLY under `tests/` and `plans/README.md` — nothing under `engine/` or `dashboard/`.
- [ ] No production source file is modified: `git diff --name-only c3e2679..HEAD -- engine dashboard` returns empty.
- [ ] `plans/README.md` status row for plan 013 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (the
  parsers, the caps, or the routes drifted since this plan was written —
  caught by the drift check).
- `tests/conftest.py` already exists — do not overwrite it; report so the
  fixture can be merged in by hand.
- The `importlib.reload` approach in Step 4 raises an import/circular-import
  error when redirecting `ATLAS_DATA_DIR`, OR the app still hits the real
  `data/atlas.db` (e.g. a row appears in the repo's real DB during the test
  run). Both mean the env-var redirection failed — report rather than pointing
  tests at the live DB.
- A `Job` field or a `DB`/`analytics` method name used in the tests does not
  exist (the introspection commands in Steps 2/4 disagree with the plan).
- Any test reveals what looks like a real bug (e.g. `/applied` accepting an
  unknown id). Do NOT fix it — characterize the current behavior, note it in
  Maintenance, and flag it for a separate plan.
- A step's verification fails twice after a reasonable fix attempt.

## Maintenance notes

For the owner of this code after the change lands:

- **The `/applied` route has no 404 guard** (`dashboard/backend/main.py:79-83`),
  unlike `/state`. The characterization test in Step 4 locks the current
  (guard-less) behavior. If a future plan adds the guard, that test must be
  updated to expect 404 — it is intentionally pinning today's contract, not
  endorsing it. Worth a separate bug plan.
- **Deferred parser coverage**: ashby, himalayas, and adzuna are out of scope
  here (no saved payloads captured). When adding them, reuse the `_StubClient`
  pattern from `tests/test_parsers.py` and add one fixture per source. The
  himalayas/adzuna feeds differ in shape from the ATS trio — capture a real
  sample before asserting.
- **Fixture freshness**: these are characterization fixtures, not contracts with
  the vendors. If a vendor changes its JSON shape in production, the fix is to
  update the parser AND refresh the fixture together — a failing parser test
  here is the intended early-warning signal.
- **Reviewer focus**: confirm the tests are genuinely network-free (no
  `httpx.Client` constructed against a real host, no write to the repo's real
  `data/atlas.db`), and that `ATLAS_DATA_DIR` redirection actually takes effect
  (the strongest check: the repo `data/atlas.db` mtime is unchanged after the
  suite runs).
