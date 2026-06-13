# Plan 019: [DIRECTION] Dashboard-triggered discover/score (design spike)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **This is a design-spike plan (STATUS: TODO).** It is deferred deliberately.
> It introduces the first *long-running, network-touching* POST in the
> dashboard backend, and the progress-reporting mechanism (poll vs SSE) is an
> open question. Do NOT ship it as a routine feature. Step 1 is a spike that
> must (a) resolve the progress-reporting decision and (b) confirm the
> dependency on Plan 014 (shared SQLite connection) is satisfied, BEFORE any
> production endpoint is added to `dashboard/backend/main.py`. If you cannot
> resolve the concurrency question (a long discover run writing to SQLite while
> the SPA polls read endpoints) with confidence, STOP and report rather than
> shipping a guess.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- dashboard/backend/main.py dashboard/frontend/src/App.tsx dashboard/frontend/src/api.ts dashboard/frontend/src/components/CommandPalette.tsx engine/discovery/runner.py engine/scoring/run.py engine/cli.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts below against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: LOW
- **Depends on**: `plans/014-shared-sqlite-connection.md`
- **Category**: direction
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

Between scheduled brain runs the cockpit (the React dashboard) is **read-only for
fresh data**: a user looking at stale results has no way to ask Atlas to go find
new jobs. The dashboard already exposes a per-JOB on-demand action — `POST
/api/jobs/{id}/prep` runs the deterministic CV+outreach build pipeline for one job
(`dashboard/backend/main.py:87-97`) — but there is no equivalent **full-refresh**
trigger to run discovery/scoring across all sources. The "Actualizar tablero"
command and the `RefreshCw` button only re-fetch existing rows; they never pull
new ones.

The discovery and scoring engines are a good fit for a button because they are
**deterministic and keyless**: `engine.discovery.runner.discover` is plain HTTP +
deterministic Python (no LLM, no SDK, no API key required — Adzuna keys are
optional and the source skips silently when unconfigured), and
`engine.scoring.run.score_jobs` is pure local computation. Exposing them as a POST
therefore stays within the README/SETUP **$0 invariant**. After this spike lands,
the user can press "buscar ahora", a discover/score run executes in the background,
and the board reflects new jobs without leaving the UI — and the team has a
documented decision on how a long-running backend job reports progress to the SPA,
which is reusable for any future on-demand job.

This plan is a **design spike**: its primary deliverable is the
progress-reporting decision plus a prototype endpoint and UI trigger, not a
polished production feature.

## Current state

The facts the executor needs, inlined.

### Files in play

- `dashboard/backend/main.py` — FastAPI app. All routes are short, synchronous,
  fast read/state-mutation handlers. The one on-demand pipeline trigger is
  `POST /api/jobs/{id}/prep`. There is **no** discover/score endpoint.
- `engine/discovery/runner.py` — `discover(db, ...)` orchestrator; keyless HTTP +
  deterministic Python; per-source try/except + health logging; everything is
  upserted so re-runs never duplicate.
- `engine/scoring/run.py` — `score_jobs(db, criteria, *, rescore=False)`; pure
  local scoring; returns `(scored, shortlisted)`.
- `engine/cli.py` — the existing `discover` and `score` typer commands; the
  pattern this endpoint should mirror at the call-site level.
- `dashboard/frontend/src/App.tsx` — top bar + `load()` refetch; owns the
  `RefreshCw` button.
- `dashboard/frontend/src/components/CommandPalette.tsx` — the "Actualizar
  tablero" command item.
- `dashboard/frontend/src/api.ts` — typed fetch client (`get`/`post` helpers +
  the `api` object).

### Exact current code

The on-demand pipeline trigger that this plan parallels —
`dashboard/backend/main.py:87-97`:

```python
@app.post("/api/jobs/{job_id}/prep")
def api_prep(job_id: str, body: PrepBody):
    from engine.cv.build import build_for_job
    from engine.outreach.build import build_outreach, write_package
    with DB() as db:
        if not db.get_job(job_id):
            raise HTTPException(404, "job not found")
        cv = build_for_job(db, job_id, language=body.language)
        build_outreach(db, job_id, language=body.language)
        write_package(db, job_id, language=body.language)
    return {"ok": True, "coverage": cv.coverage, "parse_ok": cv.parse_ok}
```

The full route surface — `dashboard/backend/main.py:39-135` — is exactly:
`GET /api/overview`, `GET /api/jobs`, `GET /api/board`, `GET /api/jobs/{job_id}`,
`POST /api/jobs/{job_id}/state`, `POST /api/jobs/{job_id}/applied`,
`POST /api/jobs/{job_id}/prep`, `POST /api/messages/{message_id}/sent`,
`GET /api/brief`, `GET /api/cv/{job_id}/{version_id}/download`,
`GET /api/health`. **No discover/score endpoint exists.** The app is created at
`main.py:23` as `app = FastAPI(title="Atlas", docs_url="/api/docs")`, with CORS
allowing the Vite dev origins (`main.py:24-27`).

The discover entry point — `engine/discovery/runner.py:28-31`:

```python
def discover(db: DB, *, sources_cfg: Optional[dict] = None,
             companies: Optional[list[CompanyTarget]] = None,
             terms: Optional[list[str]] = None,
             only: Optional[set[str]] = None) -> dict:
```

It returns a summary dict shaped (`runner.py:39`):
`{"sources": {}, "new": 0, "seen": 0, "fetched": 0, "errors": []}`, and at the end
records run metadata via `db.meta_set("last_run", ...)`, `db.meta_set("last_discover", ...)`,
`db.log_event(None, "source_run", ...)` (`runner.py:108-112`). It is keyless: Adzuna
"skips silently if unconfigured" (`runner.py:103-105`), so the run needs no secret.

The scoring entry point — `engine/scoring/run.py:9`:

```python
def score_jobs(db: DB, criteria: Criteria, *, rescore: bool = False) -> tuple[int, int]:
    """Score jobs and shortlist those above threshold. Returns (scored, shortlisted)."""
```

The CLI call-site to mirror — `engine/cli.py:72-79` (discover) and
`engine/cli.py:95-103` (score):

```python
def discover(
    only: Optional[str] = typer.Option(None, help="Comma list to limit sources: ats,jobspy,indeed,linkedin,himalayas,adzuna"),
) -> None:
    """Pull jobs from all enabled sources into the database (idempotent)."""
    from engine.discovery.runner import discover as run_discover
    only_set = {s.strip() for s in only.split(",")} if only else None
    with _db() as db:
        summary = run_discover(db, only=only_set)
```

```python
def score(
    rescore: bool = typer.Option(False, help="Re-score every job, not just newly discovered ones."),
) -> None:
    """Score fit for discovered jobs; shortlist those above the threshold."""
    from engine.config import load_criteria
    from engine.scoring.run import score_jobs
    criteria = load_criteria()
    with _db() as db:
        scored, shortlisted = score_jobs(db, criteria, rescore=rescore)
```

The frontend refresh button — `dashboard/frontend/src/App.tsx:94`:

```tsx
<button className="btn !py-1.5" onClick={load}><RefreshCw size={14} /></button>
```

…where `load` (`App.tsx:27-33`) only re-fetches existing rows:

```tsx
const load = useCallback(async () => {
  const [o, b] = await Promise.all([api.overview(), api.board()]);
  setOv(o.overview);
  setActions(o.needs_action);
  setColumns(b.columns);
  setJobs(b.jobs);
}, []);
```

The command-palette item — `dashboard/frontend/src/components/CommandPalette.tsx:39`:

```tsx
<Item onSelect={() => { onRefresh(); setOpen(false); }} icon={<RefreshCw size={14} />} text="Actualizar tablero" />
```

The typed client helpers — `dashboard/frontend/src/api.ts:71-79` (the `post`
helper) and `api.ts:82-89` (existing methods, e.g.
`prep: (id, language = "en") => post(\`/api/jobs/${id}/prep\`, { language })`).

### Conventions this plan must honor (match exactly)

These are observed in the live code; new code MUST follow them:

- **`from __future__ import annotations`** at the top of every Python module
  (see `dashboard/backend/main.py:7`, `engine/discovery/runner.py:7`).
- **typer** for CLI; **pydantic v2** `BaseModel` for request bodies — see
  `StateBody`/`PrepBody` at `main.py:30-35`. Use `Literal[...]` for constrained
  fields (as `PrepBody.language` does) rather than free strings.
- **`rich.console`** for CLI output (see `engine/cli.py` `console`/`Table` use).
- **sqlite3** access is via the `DB()` context manager (`with DB() as db:`),
  always **PARAMETERIZED** queries, WAL mode. See `main.py:101-105` for the
  parameterized UPDATE pattern and the engine's `engine/db/models.py`.
- **`@dataclass`** for result objects in the engine layer.
- Engine functions return either a **summary dict** (discover) or a **typed
  tuple** (score) — surface those back to the client verbatim, do not invent a
  new shape.
- **Frontend**: typed `api` client only — never raw `fetch` in components. Add a
  method to the `api` object in `api.ts` mirroring `prep`/`setState`.
- **Spanish UI copy** (the dashboard is in Spanish: "Actualizar tablero",
  "buscar ahora", "última corrida"). New UI labels in Spanish.

### Design constraints inlined from the engine docs

- **$0 invariant** (README/SETUP): the dashboard and discovery/scoring path must
  stay **deterministic-only — no LLM, no Anthropic SDK, no paid API**. `discover`
  and `score_jobs` already satisfy this. Any change that introduces an LLM/SDK
  call into this endpoint VIOLATES the invariant — out of scope and a STOP
  condition.
- **Plan 014 dependency**: `plans/014-shared-sqlite-connection.md` is itself a
  TODO design spike (it resolves whether/how FastAPI requests share one SQLite
  connection and the thread-safety model). A long-running discover POST that
  writes to SQLite **while** the SPA polls read endpoints wants that
  concurrency/connection model settled first. Do not start production code here
  until 014's model is decided.

## Commands you will need

| Purpose            | Command                                              | Expected on success            |
|--------------------|------------------------------------------------------|--------------------------------|
| Python tests       | `uv run --extra dev pytest`                          | `9 passed` (today's baseline)  |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`      | exit 0, no errors              |
| Frontend build     | `npm --prefix dashboard/frontend run build`          | exit 0, build succeeds         |
| Drift check        | `git diff --stat c3e2679..HEAD -- <in-scope paths>`  | no unexpected changes          |

Do **NOT** use bare `pytest`: it hits a global interpreter missing `docx`,
`rapidfuzz`, and `reportlab` and falsely fails 2 tests. Always
`uv run --extra dev pytest`.

## Scope

**In scope** (the only files you should modify):
- `dashboard/backend/main.py` — add the new endpoint(s).
- `dashboard/frontend/src/api.ts` — add the typed client method(s).
- `dashboard/frontend/src/App.tsx` — wire the "buscar ahora" action + in-flight
  indicator.
- `dashboard/frontend/src/components/CommandPalette.tsx` — add the palette item.
- `tests/test_engine.py` — add a backend endpoint test (model new tests after the
  existing ones in this file).

**Out of scope** (do NOT touch, even though they look related):
- `engine/discovery/runner.py`, `engine/scoring/run.py`, `engine/cli.py` — reuse
  these as-is; the endpoint calls them. Changing the engine signatures is a
  separate concern.
- Any LLM/Anthropic SDK integration — would violate the $0 invariant.
- `engine/db/models.py` connection model — that is Plan 014's job; do not
  pre-empt it here.
- The public shape of existing routes/responses — the SPA depends on them.

## Git workflow

- Branch: `advisor/019-dashboard-trigger-discover-spike` (off the latest `main`).
- Commit per logical unit (spike note → backend endpoint → frontend wiring →
  test). Match the repo's existing concise, imperative commit style (e.g.
  `git log` shows `advisor: surface [confirma] gaps in CV audit`,
  `Add light/dark theme toggle + native PDF export (reportlab)`).
- Do **NOT** push or open a PR. Merge to `main` is the operator's decision.

## Steps

### Step 1 (SPIKE — required before any production code): resolve progress reporting + confirm the 014 dependency

This step produces a **decision**, not shipping code. Do not skip it.

1. Confirm `plans/014-shared-sqlite-connection.md` has a settled connection /
   thread-safety model. If 014 is still unresolved (status not DONE and no chosen
   approach recorded), **STOP** — this plan is blocked on it. A long discover run
   writing to SQLite while the SPA polls read endpoints needs that model first.
2. Decide the **progress-reporting mechanism**, choosing between (and recording
   the rationale in the PR description / a comment at the top of the new
   endpoint):
   - **(A) Fire-and-forget + poll**: endpoint launches the run in a FastAPI
     `BackgroundTasks` task and returns `202 {"started": true}` immediately; the
     SPA polls an existing read endpoint (`GET /api/overview` — note `overview`
     already exposes `last_run`, see `App.tsx:82`) or a small new
     `GET /api/discover/status` that reports in-flight state. Simplest; no new
     transport.
   - **(B) Synchronous**: endpoint runs `discover` then `score_jobs` inline and
     returns the summary. Simplest to reason about but blocks the request for the
     full run (up to `per_source_timeout_s`, default 45s, per source per
     `runner.py:37`) — only acceptable if the run is reliably short.
   - **(C) SSE / streaming**: richer progress, but introduces a new transport and
     more surface area; likely overkill for a single-user localhost tool.
   - Default recommendation for a single-user localhost cockpit: **(A)** with a
     simple in-flight boolean exposed on `GET /api/overview` or a tiny status
     route, deferring SSE.
3. Decide whether to expose **one** endpoint that does discover-then-score, or
   **two** (`POST /api/discover`, `POST /api/score`). Recommendation: one
   `POST /api/discover` that runs discover then `score_jobs` (so a refresh both
   pulls and scores), keeping `/api/score` as a possible later split.

**Verify**: a written decision exists (in the PR body or as a docstring/comment
at the new endpoint) naming the chosen option and confirming 014 is satisfied.
There is no command gate for a decision; the gate is that Steps 2+ may not begin
until this is recorded.

### Step 2: Add the backend endpoint (deterministic, keyless)

In `dashboard/backend/main.py`, add a `POST /api/discover` route mirroring the
`api_prep` pattern (`main.py:87-97`). Implement the mechanism chosen in Step 1.

If **(A) background**: accept `BackgroundTasks`, schedule a function that opens
its own `with DB() as db:` and calls
`engine.discovery.runner.discover(db, only=...)` then
`engine.scoring.run.score_jobs(db, load_criteria())`, return
`202 {"started": True}`. Use lazy imports inside the handler (the codebase does
this: `main.py:89-90`). Reuse the `only` semantics from `cli.py:77`
(comma list → `set`).

If **(B) synchronous**: run both inline inside `with DB() as db:` and return the
`discover` summary dict plus `{"scored": ..., "shortlisted": ...}` from
`score_jobs`.

Constraints:
- No LLM/SDK import anywhere in this handler ($0 invariant).
- Match conventions: pydantic v2 body model if it takes params (e.g. an optional
  `only` field), `from __future__ import annotations` already present at
  `main.py:7`.
- Place the route with the other `/api/*` routes, BEFORE the static mount at
  `main.py:140-142` (the comment there warns the mount must stay last).

**Verify**:
- `uv run --extra dev pytest` → `9 passed` (no regression; new test added in
  Step 5 raises this count).
- Manual: start the backend
  (`uv run uvicorn dashboard.backend.main:app --port 8787`) and
  `curl -s -X POST http://127.0.0.1:8787/api/discover` returns HTTP 200/202 with
  the agreed JSON shape (and no traceback in the server log).

### Step 3: Add the typed client method

In `dashboard/frontend/src/api.ts`, add a method to the `api` object mirroring
`prep`/`markApplied` (`api.ts:85-87`), e.g.:

```ts
discover: () => post<{ started: boolean }>("/api/discover"),
```

(Adjust the return type to the shape chosen in Step 1/2.) Use the existing `post`
helper (`api.ts:71-79`); never call `fetch` directly from a component.

**Verify**: `npm --prefix dashboard/frontend run typecheck` → exit 0.

### Step 4: Wire the UI trigger + in-flight indicator

In `dashboard/frontend/src/App.tsx`:
- Add a `searching` boolean state and a `buscarAhora()` handler that sets
  `searching = true`, awaits `api.discover()`, then calls `load()` (the existing
  refetch at `App.tsx:27-33`) — or, for mechanism (A), starts polling `load()`
  until the run reports done — and finally sets `searching = false`.
- Add a "buscar ahora" button to the top bar next to the existing `RefreshCw`
  button (`App.tsx:94`); show an in-flight indicator (spinner/disabled state)
  while `searching` is true. Do NOT remove the existing refresh button — it
  still serves the cheap re-fetch.

In `dashboard/frontend/src/components/CommandPalette.tsx`, add a palette `Item`
next to "Actualizar tablero" (`CommandPalette.tsx:39`) labelled "buscar ahora"
that invokes the same action (thread a new prop through the way `onRefresh` is
threaded — see `CommandPalette.tsx:7,13`).

**Verify**:
- `npm --prefix dashboard/frontend run typecheck` → exit 0.
- `npm --prefix dashboard/frontend run build` → exit 0, build succeeds.

### Step 5: Add a backend endpoint test

In `tests/test_engine.py`, add a test modelled after the existing tests in that
file. Use FastAPI's `TestClient` against `dashboard.backend.main:app`. Cover:
- happy path: `POST /api/discover` returns the agreed status code and JSON shape
  (monkeypatch `engine.discovery.runner.discover` and
  `engine.scoring.run.score_jobs` to deterministic stubs so the test makes **no
  network calls** — the real run hits HTTP);
- that the handler imports **no** Anthropic/LLM module (assert by inspecting the
  handler's module imports, or simply that the stubbed deterministic path is the
  only one taken).

**Verify**: `uv run --extra dev pytest` → `10 passed` (the 9 baseline + 1 new).

## Test plan

- New test in `tests/test_engine.py`, modelled structurally on the existing tests
  there. Cases: (1) `POST /api/discover` happy path with stubbed engine fns
  returning a canned summary/tuple — assert status code and JSON shape;
  (2) network isolation — the test must not perform real HTTP (stub
  `runner.discover`); (3) determinism/$0 — no LLM/SDK code path is reachable.
- Use FastAPI `TestClient` (the dashboard is a FastAPI app, `main.py:23`).
- Verification: `uv run --extra dev pytest` → all pass, including the 1 new test
  (count goes 9 → 10).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] A recorded Step 1 decision exists (PR body or endpoint docstring) naming
      the progress-reporting mechanism and confirming Plan 014's model is settled.
- [ ] `uv run --extra dev pytest` → `10 passed` (9 baseline + 1 new endpoint test).
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0.
- [ ] `npm --prefix dashboard/frontend run build` exits 0.
- [ ] `grep -rnE "anthropic|claude|openai|langchain" dashboard/backend/main.py`
      returns no matches (the $0/deterministic invariant holds for the new code).
- [ ] `grep -n "/api/discover" dashboard/backend/main.py dashboard/frontend/src/api.ts`
      shows the endpoint and the client method both present.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row for 019 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (the
  codebase drifted since `c3e2679` — the drift-check diff is non-empty for an
  in-scope file and the excerpt no longer matches).
- `plans/014-shared-sqlite-connection.md` is still unresolved (no chosen
  connection/thread-safety model) — this plan is **blocked** on 014; do not ship
  a long-running write POST against an unsettled connection model.
- Implementing the endpoint appears to require an LLM, the Anthropic SDK, or any
  paid API call — that violates the $0 invariant; stop rather than break it.
- A discover run inside the request triggers SQLite "database is locked" or
  concurrency errors while the SPA polls read endpoints — that is the exact risk
  014 exists to resolve; stop and report.
- The fix appears to require modifying `engine/discovery/runner.py`,
  `engine/scoring/run.py`, or `engine/db/models.py` (all out of scope here).
- Any verification command fails twice after a reasonable fix attempt.
- You discover the assumption "`discover` and `score_jobs` are keyless and need no
  secret" is false (e.g. a source now hard-requires a key) — report it.

## Maintenance notes

For the human/agent who owns this code after the change lands:

- This is the **first long-running, network-touching POST** in the dashboard
  backend. Any future on-demand backend job (re-tail all, bulk re-score) should
  reuse the progress-reporting mechanism decided in Step 1 rather than inventing
  another.
- If Plan 014 changes the connection model later, revisit how the background
  discover task opens its `DB()` — it must stay consistent with whatever 014
  settles.
- A reviewer should scrutinize: (1) that no LLM/SDK import sneaks into the new
  handler ($0 invariant); (2) that the static mount stays last in `main.py`
  (the new route must be registered before `main.py:140-142`); (3) that the test
  stubs the engine functions so CI never makes real network calls; (4) that the
  UI's in-flight state cannot get stuck `true` if the POST fails.
- Deferred out of this spike (deliberately): SSE/streaming progress (option C);
  splitting discover and score into two separate buttons; surfacing per-source
  health from the run summary in the UI. Revisit if users want live progress
  detail beyond a spinner.
