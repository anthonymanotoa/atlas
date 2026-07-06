# Plan 021: Close the cross-profile race windows around profile switching

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 413ae10..HEAD -- dashboard/backend/main.py engine/paths.py tests/test_backend_api.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `413ae10`, 2026-07-06

## Why this matters

Atlas hosts several **independent profiles** (different real people, each with their own
CV, criteria and SQLite DB under `profiles/<id>/`), and the dashboard can switch the
active profile at runtime. The active profile is **process-global mutable state**
(module globals in `engine/paths.py`), while the FastAPI backend serves requests on
multiple worker threads. Three code paths mutate or read that global state without
synchronization, so a profile switch that lands at the wrong moment can mix two
profiles' data: one person's CV tailored against another person's job row, a portfolio
built from profile A's CV but persisted into profile B's DB, or — worst — a background
discover run that permanently re-points the whole process at the *old* profile while
the registry and shared DB point at the new one. For a tool whose promise is "cada
perfil queda **aislado**", cross-profile contamination is the highest-impact bug class
in the codebase.

## Current state

Relevant files:

- `engine/paths.py` — single source of truth for every path; profile switch re-points
  module globals (`_apply()` / `set_profile()`).
- `dashboard/backend/main.py` — FastAPI backend; one shared SQLite connection `_DB`
  serialized behind `_DB_LOCK` (plan 014); the profile-switch endpoint; the discover
  background task.
- `engine/db/models.py` — `DB()` resolves `paths.DB_PATH` **late** (at construction).
- `tests/test_backend_api.py` — existing TestClient suite, built on the `atlas_app`
  fixture from `tests/conftest.py`.

How the pieces work today:

`engine/paths.py:93-99` — the switch mutates module globals, documented as
single-worker process-global state:

```python
def set_profile(profile_id: str) -> None:
    """Point all paths at a specific profile. Used by the dashboard switch and CLI/brain.

    Re-points the module globals in-process; the next short-lived ``DB()`` opens the new
    profile's database. Single uvicorn worker only — the pointer is process-global state.
    """
    _apply(profile_id)
```

`dashboard/backend/main.py:38-57` — the shared connection and the lock. Note that
`get_db()` **holds `_DB_LOCK` for the entire request** (the `yield` is inside the
`with`), so any handler using `Depends(get_db)` is fully serialized:

```python
_DB: DB | None = None
_DB_LOCK = Lock()
...
def get_db():
    """Yield the process-wide DB, serialized so sync handlers never race the connection."""
    with _DB_LOCK:
        yield _DB
```

`dashboard/backend/main.py:776-794` — the switch endpoint. **Race (a)**: it mutates the
registry and the path globals (lines 788-789) *before* acquiring `_DB_LOCK` (line 790).
A request thread that wins the lock in that window runs with the OLD `_DB` and the NEW
paths — e.g. `POST /api/jobs/{id}/prep` would tailor the new profile's `master_cv.yaml`
against the old profile's job row:

```python
@app.post("/api/profile", dependencies=[Depends(require_trusted_origin)])
def api_switch_profile(body: ProfileBody):
    ...
    profiles.set_active(body.id)  # persist registry.json "active"
    paths.set_profile(body.id)  # re-point the path globals
    with _DB_LOCK:  # reopen the shared connection on the new profile's DB
        if _DB is not None:
            _DB.close()
        _DB = DB(check_same_thread=False)
    return {"ok": True, "active": body.id}
```

`dashboard/backend/main.py:328-366` — the discover background task. **Race (c)**: it
calls `paths.set_profile(profile_id)` from the background thread (line 337-338). If the
user switches the dashboard to profile B while a discover for profile A is running, the
background thread flips the process-global paths BACK to A — and nothing ever restores
B. From then on `registry.json` and `_DB` say B while every `paths.*` read (config
loads, outbox writes) says A, silently crossing profiles until the next switch:

```python
def _run_discover_and_score(only: set[str] | None, profile_id: str | None) -> None:
    global _discovering
    try:
        ...
        # Re-pin the profile captured at enqueue time so a concurrent dashboard switch
        # can't make this run land in another profile's DB/criteria.
        if profile_id is not None:
            paths.set_profile(profile_id)
        with DB() as db:  # own connection — see note above
            run_discover(db, only=only)
            score_jobs(db, load_criteria(), rescore=True)
```

**Race (b)** — handlers that read `paths.*` or path-dependent config but do NOT hold
`_DB_LOCK`, so a concurrent switch flips their inputs mid-request:

- `main.py:375-379` `api_brief` — reads `paths.OUTBOX_DIR / "MORNING_BRIEF.md"`, no lock.
- `main.py:444-…` `api_cv_library` — no `Depends(get_db)` (see route listing), reads paths.
- `main.py:598-618` `api_portfolio_research` — calls `load_master_cv()`, `load_criteria()`,
  `load_cv_layout()`, `load_ontology()`, `domain_of(paths.PROFILE_ID)`, no lock.
- `main.py:569-583` `api_portfolio_generate` — deliberately lock-free (a ~15s network
  call must not freeze the API; documented in its docstring), but it reads
  `load_master_cv()` (paths-dependent) at line 580 and persists with `with DB()` (late
  path binding) at line 581 — a mid-generate switch builds from one profile's CV and
  writes the row into the other profile's DB.

`engine/db/models.py:37-43` — why late binding matters (any `DB()` constructed after a
flip opens the *new* profile's database):

```python
class DB:
    def __init__(self, path: Path | str | None = None, *, check_same_thread: bool = True):
        # Read paths.DB_PATH late so DB() follows the active profile; an explicit path
        # (e.g. in tests) still wins ...
        if path is None:
            path = paths.DB_PATH
```

Conventions that apply (match them):

- Comments in `main.py` explain *why* a locking decision is sound (see the plan-014
  block comment at `main.py:29-37`) — keep that style for any new lock/guard.
- Errors surface as `HTTPException(status, "lower-case reason")` (see
  `main.py:784-787`).
- Background-task failures are recorded, not raised (see `main.py:345-350`
  `db.log_event(None, "error", {...})`).
- Tests use the `atlas_app` fixture (`tests/conftest.py:17-36`) + FastAPI `TestClient`;
  model new tests on `tests/test_backend_api.py`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Python tests | `uv run pytest` | all pass (baseline 180 + your new ones) |
| One test file | `uv run pytest tests/test_backend_api.py -q` | all pass |
| Lint | `uv run ruff check .` | exit 0 |
| Format | `uv run ruff format --check .` | exit 0 |
| Full gate | `./scripts/check.sh` | `✓ All checks passed.` |

## Scope

**In scope** (the only files you should modify):

- `dashboard/backend/main.py`
- `tests/test_backend_api.py`

**Out of scope** (do NOT touch, even though they look related):

- `engine/paths.py` — the process-global pointer design is documented and intentional
  ("Single uvicorn worker only"); this plan serializes its *callers*, it does not
  redesign the pointer.
- `engine/db/models.py` — late path binding is load-bearing for the CLI and tests.
- `brain/run_brain.py` and `engine/cli.py` — they pin the profile once at startup
  (`--profile` / `$ATLAS_PROFILE`) in a single-threaded process; no race exists there.
- The frontend — no UI change needed; a 409 on switch is already surfaced by the
  generic error toast.

## Git workflow

- Branch: `advisor/021-profile-switch-race` (repo uses short-lived feature branches).
- Conventional commits, e.g. `fix(backend): serialize profile switch against in-flight work`
  (match the style of `git log --oneline`, e.g. `fix(config): split frontmatter only on bare --- fence lines`).
- Never `git add .` / `git add -A` — add only the files you touched, by name.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Make the switch atomic and refuse it while background work is in flight

In `dashboard/backend/main.py`:

1. Add a module-level busy flag next to the existing `_DISCOVER_LOCK` block
   (`main.py:324-325`): a counter `_BUSY_JOBS = 0` guarded by the existing
   `_DISCOVER_LOCK` (rename nothing; the lock already guards `_discovering`).
   Add a tiny helper pair, with a why-comment in the plan-014 style:

   ```python
   def _busy_acquire() -> None:
       global _BUSY_JOBS
       with _DISCOVER_LOCK:
           _BUSY_JOBS += 1

   def _busy_release() -> None:
       global _BUSY_JOBS
       with _DISCOVER_LOCK:
           _BUSY_JOBS = max(0, _BUSY_JOBS - 1)
   ```

2. In `api_switch_profile` (`main.py:776-794`), move the ENTIRE switch inside
   `_DB_LOCK`, and reject while background work runs:

   ```python
   @app.post("/api/profile", dependencies=[Depends(require_trusted_origin)])
   def api_switch_profile(body: ProfileBody):
       global _DB
       if not profiles.valid_id(body.id):
           raise HTTPException(400, "invalid profile id")
       if not profiles.exists(body.id):
           raise HTTPException(404, "unknown profile")
       with _DISCOVER_LOCK:
           if _discovering or _BUSY_JOBS:
               raise HTTPException(409, "background work in progress — retry when it finishes")
       with _DB_LOCK:  # atomic vs. every get_db request: registry + paths + conn flip together
           profiles.set_active(body.id)
           paths.set_profile(body.id)
           if _DB is not None:
               _DB.close()
           _DB = DB(check_same_thread=False)
       return {"ok": True, "active": body.id}
   ```

   (Holding `_DB_LOCK` around the whole mutation closes races (a) and (b) for every
   handler that uses `Depends(get_db)`, because those handlers hold the same lock for
   their full duration.)

**Verify**: `uv run pytest tests/test_backend_api.py -q` → existing tests still pass.

### Step 2: Stop the discover background task from mutating process globals

In `_run_discover_and_score` (`main.py:328-353`):

1. Delete the re-pin (`if profile_id is not None: paths.set_profile(profile_id)`).
2. Replace it with an abort guard — if the active profile no longer matches the one
   captured at enqueue time, record an event and return without running:

   ```python
   # The profile was pinned at enqueue time. A switch is refused while we run
   # (api_switch_profile checks _discovering), so a mismatch here means the pin
   # raced a switch — abort rather than flip process-global paths from a bg thread.
   if paths.PROFILE_ID != profile_id:
       with DB() as db:
           db.log_event(None, "error", {"stage": "discover_bg", "error": "aborted: profile switched"})
       return
   ```

   Keep the `finally: _discovering = False` exactly as is.

**Verify**: `uv run pytest tests/test_backend_api.py -q` → pass.

### Step 3: Guard the busy window of `api_portfolio_generate`

`api_portfolio_generate` (`main.py:569-583`) must stay lock-free during the ~15s build
(its docstring explains why — keep it). Bracket it with the busy flag so a switch
cannot land mid-generate:

```python
def api_portfolio_generate(body: PortfolioBody):
    ...
    _busy_acquire()
    try:
        version = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = generate_portfolio(load_master_cv(), version=version, include_github=body.include_github)
        with DB() as db:  # own connection — does not hold the shared API lock
            pid = db.add_portfolio(version=version, path_html=str(path))
        return {"ok": True, "id": pid, "version": version, "path": str(path)}
    finally:
        _busy_release()
```

**Verify**: `uv run pytest -q` → all pass.

### Step 4: Serialize the read-only paths-reading GET endpoints

These three handlers read `paths.*`-dependent state without the lock. Give each the
shared-lock dependency so a switch can't flip their inputs mid-request. They don't need
the DB value — use an underscore dependency and say why:

- `api_brief` (`main.py:375-379`)
- `api_cv_library` (`main.py:444`)
- `api_portfolio_research` (`main.py:598-618`)

Pattern (apply to all three):

```python
@app.get("/api/brief")
def api_brief(_: DB = Depends(get_db)):  # unused DB; holds _DB_LOCK so a profile switch can't flip paths mid-read
```

**Verify**: `uv run pytest -q` → all pass; `uv run ruff check .` → exit 0 (the unused
argument named `_` is lint-clean).

### Step 5: Regression tests

Add to `tests/test_backend_api.py` (use the existing `atlas_app` fixture + `TestClient`
imports already present in that file):

1. `test_switch_profile_refused_while_discovering` — set
   `backend_main._discovering = True` (import the reloaded module from the fixture via
   `import dashboard.backend.main as backend_main` — note the conftest reloads it, so
   fetch the module with `importlib.import_module` after the fixture, or expose it the
   same way existing tests do), POST `/api/profile` with a valid body, assert `409`.
   Reset the flag in a `finally`.
2. `test_discover_bg_aborts_on_profile_mismatch` — call
   `backend_main._run_discover_and_score(None, "some-other-profile")` directly with
   `paths.PROFILE_ID` left as `None` (legacy mode in tests); monkeypatch
   `engine.paths.set_profile` with a spy that raises `AssertionError("must not be called")`;
   assert it does not raise and that no discovery ran (monkeypatch
   `engine.discovery.runner.discover` with a spy; assert not called).
3. `test_switch_profile_unknown_id_404` — if an equivalent doesn't already exist,
   POST `/api/profile` with `{"id": "nope"}` → 404 (pins the validation order after the
   refactor).

**Verify**: `uv run pytest tests/test_backend_api.py -q` → all pass, including 3 new tests.

## Test plan

- New tests listed in Step 5, in `tests/test_backend_api.py`, modeled structurally on
  the existing tests in that file (TestClient + `atlas_app` fixture).
- Full suite: `uv run pytest` → everything green (baseline 180 + new).
- The races themselves are thread-timing bugs; the tests pin the *mechanisms* (409 while
  busy, no global mutation from the bg thread, validation order), which is what an
  executor can verify deterministically.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run pytest` exits 0; the 3 new tests exist and pass
- [ ] `uv run ruff check dashboard/backend/main.py tests/test_backend_api.py` and
      `uv run ruff format --check dashboard/backend/main.py tests/test_backend_api.py`
      exit 0 (scoped to the files this plan touches — see note below)
- [ ] `grep -n "paths.set_profile" dashboard/backend/main.py` shows exactly ONE call —
      the one inside `api_switch_profile` under `_DB_LOCK` (none in the background task)
- [ ] `grep -n "set_active" dashboard/backend/main.py` shows the call inside the
      `with _DB_LOCK:` block
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

> **Note on the whole-repo gate**: `./scripts/check.sh` (which runs `uv run ruff check .`
> repo-wide) currently fails independent of this plan, on 3 pre-existing UP037 errors in
> `engine/portfolio/prompt.py` — confirmed byte-identical to this plan's own baseline
> commit `413ae10` (`git diff 413ae10..HEAD -- engine/portfolio/prompt.py` is empty).
> That file is out of scope for plan 021 (see Scope) and is already tracked by a sibling
> effort (worktree `atlas-ruff-format-realign`, branch `chore/ruff-format-realign`,
> ~8 files repo-wide). The Done Criteria above are scoped to the files this plan actually
> touches so they can be verified in isolation; `./scripts/check.sh` should be re-run
> (and is expected to pass) once `chore/ruff-format-realign` lands.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (drift).
- Moving `profiles.set_active` under `_DB_LOCK` deadlocks any existing test — that
  would mean some handler calls the switch endpoint re-entrantly while holding the
  lock; report which test.
- `api_portfolio_generate` turns out to need more than the busy-bracket (e.g. you find
  another late `paths.*` read after the DB write) — report instead of extending scope.
- You are tempted to modify `engine/paths.py` to fix this "properly" (e.g. contextvars).
  That is a larger design change the maintainer must decide — report it as a suggestion.

## Maintenance notes

- Any NEW endpoint that reads `paths.*` or `engine.config.load_*` must either use
  `Depends(get_db)` (serializing) or bracket itself with `_busy_acquire()/_busy_release()`
  if it's long-running. A reviewer should check exactly this on future backend PRs.
- If the dashboard ever moves to multiple uvicorn workers, the whole process-global
  design (paths + `_DB`) breaks — `engine/paths.py`'s docstring says single worker only;
  that would be the moment to move the active profile into a per-request dependency.
- Deferred deliberately: making the CLI/brain race-proof (they pin once at startup in
  single-threaded processes — no race exists).
