# Plan 014: Reuse one SQLite connection across FastAPI requests

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **This is a design-spike plan (STATUS: TODO).** It is deferred deliberately
> because the threading model is unresolved (see "STOP conditions / Open
> questions"). Do NOT implement it as a routine refactor. Step 1 is a spike
> that must resolve the open questions and produce a chosen approach BEFORE any
> production code in `dashboard/backend/main.py` or `engine/db/models.py` is
> changed. If the spike cannot resolve the thread-safety question with
> confidence, STOP and report rather than shipping a guess.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- dashboard/backend/main.py engine/db/models.py tests/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: perf
- **Planned at**: commit `c3e2679`, 2026-06-13
- **Finding**: PERF-01 (HIGH)

## Why this matters

The dashboard backend opens a brand-new SQLite connection on **every single
HTTP request** via `with DB() as db:`. Each `DB()` construction does real work:
it connects, sets three PRAGMAs, then runs `init_schema()` which reads
`schema.sql` off disk and executes the full script — **9 `CREATE TABLE IF NOT
EXISTS` + 10 `CREATE INDEX IF NOT EXISTS`** — on every request. The single-page
app fires `/api/overview` **and** `/api/board` on initial load, and re-fires
them after every mutation (state change, mark-applied, prep). So a single user
click triggers two full schema re-parses plus two disk reads of `schema.sql`,
none of which change anything after the first run. The win: do the schema
init **once** at process startup and reuse a long-lived connection, removing the
per-request disk read and ~19 idempotent DDL statements from the hot path.

This is filed as a **design spike**, not a ready-to-code refactor, because
SQLite connections are not thread-safe by default and FastAPI/uvicorn runs sync
endpoints on a thread pool — naively sharing one `sqlite3.Connection` will raise
`SQLite objects created in a thread can only be used in that same thread`. The
spike must choose and justify a threading model before touching production code.

## Current state

The relevant files:

- `dashboard/backend/main.py` — FastAPI app. Every endpoint opens its own
  `DB()` via a `with` block. The per-request pattern spans the API section
  (lines 38–138).
- `engine/db/models.py` — the `DB` class. `__init__` connects + sets PRAGMAs +
  calls `init_schema()` (lines 33–49 below). `init_schema()` runs the full
  `schema.sql` via `executescript`.
- `engine/db/schema.sql` — the idempotent schema; **9 `CREATE TABLE IF NOT
  EXISTS`, 10 `CREATE INDEX IF NOT EXISTS`** (verified at planned-at commit).
- `tests/test_engine.py` — the existing test suite (9 tests). New tests for this
  plan are modeled after these. Its DB fixture is the structural pattern to copy.

### `dashboard/backend/main.py` — per-request `with DB()` (the hot path)

The app is constructed at module top, then every endpoint opens its own
connection. Representative excerpts (the pattern repeats for all 11 endpoints):

```python
# dashboard/backend/main.py:22-26
app = FastAPI(title="Atlas", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)
```

```python
# dashboard/backend/main.py:38-41
@app.get("/api/overview")
def api_overview():
    with DB() as db:
        return {"overview": analytics.overview(db), "needs_action": analytics.needs_action(db)}
```

```python
# dashboard/backend/main.py:50-56
@app.get("/api/board")
def api_board():
    """Jobs grouped by the columns shown on the kanban board."""
    columns = ["shortlisted", "tailored", "ready", "applied", "responded", "interview", "offer"]
    with DB() as db:
        return {"columns": columns,
                "jobs": {c: db.list_jobs(state=c) for c in columns}}
```

Other endpoints follow the identical `with DB() as db:` shape:
`api_jobs` (44–47), `api_job` (59–65), `api_set_state` (68–76),
`api_mark_applied` (79–83), `api_prep` (86–96), `api_mark_sent` (99–105),
`api_cv_download` (114–126). `api_brief` (108–111) and `health` (129–131) do
**not** touch the DB. The static-file mount is last (134–138) and must stay last.

Note `api_mark_sent` reaches into `db.conn` directly:

```python
# dashboard/backend/main.py:99-105
@app.post("/api/messages/{message_id}/sent")
def api_mark_sent(message_id: int):
    with DB() as db:
        db.conn.execute("UPDATE messages SET state='sent', sent_at=? WHERE id=?",
                        (now_iso(), message_id))
        db.conn.commit()
    return {"ok": True}
```

There is currently **no FastAPI dependency and no lifespan/startup handler** in
this file — connections exist only inside the per-request `with` blocks.

### `engine/db/models.py` — DB construction does schema init every time

```python
# engine/db/models.py:33-49
class DB:
    def __init__(self, path: Path | str = DB_PATH):
        ensure_dirs()
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.init_schema()

    # ── lifecycle ────────────────────────────────────────────────────────────
    def init_schema(self) -> None:
        self.conn.executescript(_SCHEMA.read_text())
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "DB":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
```

`sqlite3.connect(...)` is called with **default args**, i.e.
`check_same_thread=True`. The PRAGMAs set WAL, foreign keys, and a 5s busy
timeout (these are per-connection and must be preserved on any shared/pooled
connection). `__enter__`/`__exit__` make `DB` a context manager whose `__exit__`
closes the connection — the contract any shared-connection design must not break
for the CLI callers (see "Out of scope").

### Conventions this plan must match (state them, then follow them)

- `from __future__ import annotations` at the top of every module (present in
  both `main.py:7` and `models.py:11`).
- **typer** CLI, **pydantic v2** models (`StateBody`/`PrepBody` in `main.py:29-34`
  subclass `BaseModel`), **rich.console** for CLI output.
- DB access: `sqlite3` with **parameterized** queries (`?` placeholders — never
  string interpolation) and **WAL** journal mode. See `models.py:38-40` and
  `get_job` at `models.py:58-59`.
- Result objects elsewhere in the engine are `@dataclass`; tailoring uses
  UPSERT + COALESCE gap-fill and **sha1 16-char natural keys** (`compute_job_id`).
  None of these are touched here but new code must not contradict them.
- Tests live in `tests/test_engine.py` and are **network-free**. The DB fixture
  to copy:

```python
# tests/test_engine.py:17-19
@pytest.fixture
def db(tmp_path: Path) -> DB:
    return DB(tmp_path / "test.db")
```

## Commands you will need

| Purpose            | Command                                              | Expected on success            |
|--------------------|------------------------------------------------------|--------------------------------|
| Python tests       | `uv run --extra dev pytest`                          | `9 passed` (10+ after Step 3)  |
| Run a single test  | `uv run --extra dev pytest tests/test_engine.py -k <name>` | the named test passes    |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`      | exit 0, no errors              |
| Frontend build     | `npm --prefix dashboard/frontend run build`          | exit 0, build artifacts emitted|
| Drift check        | `git diff --stat c3e2679..HEAD -- dashboard/backend/main.py engine/db/models.py tests/` | (empty, or compare excerpts) |

Do **NOT** run a bare `pytest`: the global interpreter is missing `docx`,
`rapidfuzz`, and `reportlab`, which makes 2 tests falsely fail. Always use
`uv run --extra dev pytest`, which today reports exactly `9 passed`.

The frontend is not modified by this plan, but run typecheck + build once at the
end to confirm nothing regressed (the backend serves the built frontend).

## Scope

**In scope** (the only files you may modify):
- `dashboard/backend/main.py`
- `engine/db/models.py`
- `tests/test_engine.py` (add new tests here, matching the existing pattern)

**Out of scope** (do NOT touch, even though they look related):
- `engine/db/schema.sql` — the schema is already idempotent; do not change it.
- The CLI / typer entrypoints and any non-FastAPI caller of `DB()` — they
  construct `DB()` as a short-lived `with` block and depend on `__init__`
  running `init_schema()`. Any change to `DB.__init__` or `init_schema()`
  semantics that breaks the standalone `DB()` contract is out of scope; the
  shared-connection logic must live in the FastAPI layer (or be strictly
  additive/opt-in on `DB`) so CLI behavior is unchanged.
- The public JSON response shapes of every `/api/*` endpoint — the SPA depends
  on them. Performance only; bytes on the wire must be identical.
- `dashboard/frontend/**` — no frontend changes.

## Git workflow

- Branch: `advisor/014-shared-sqlite-connection` off the latest `main`.
- Commit per logical unit. Match the repo's terse, imperative commit style
  (e.g. from `git log`: `advisor: surface [confirma] gaps in CV audit`,
  `Add light/dark theme toggle + native PDF export (reportlab)`).
- **Do NOT push and do NOT open a PR.** The operator merges explicitly.
- Stage only the files this session touched, by name (`git add <file> ...`) —
  never `git add .` / `git add -A`.

## Steps

### Step 1 (SPIKE — required before any production edit): resolve the threading model

This is the reason the plan is deferred. Do not write the shared-connection code
until this step produces a written decision. Investigate and decide:

1. **How uvicorn runs these endpoints.** All `/api/*` handlers here are
   **sync** `def` functions, so Starlette runs them in an anyio worker
   **thread pool** — different requests may hit different threads. A single
   `sqlite3.Connection` made with the default `check_same_thread=True` will
   raise `SQLite objects created in a thread can only be used in that same
   thread` the moment a second thread uses it.
2. **Pick exactly one approach** and justify it:
   - **(A) One shared connection** created with `sqlite3.connect(..., check_same_thread=False)`
     guarded by a `threading.Lock` around every `execute`/`commit`. Simplest;
     serializes all DB access (acceptable for a single-user localhost app).
   - **(B) A tiny per-thread connection cache** (e.g. `threading.local` or a
     small pool), each connection created once and reused, schema init done once
     globally. Higher concurrency, more moving parts.
   Decide whether **WAL + a single writer** (approach A) is sufficient for this
   workload (it is single-user, localhost). Default recommendation: **approach A**
   for its simplicity unless the spike finds a concrete blocker.
3. **Connection lifecycle on `--reload`.** The dev server runs with `--reload`;
   confirm the chosen lifecycle (lifespan startup/shutdown) re-creates the
   connection cleanly on reload and closes it on shutdown without leaking WAL
   handles.

**Verify**: Produce a short written decision (in the PR description or a comment
at the top of the new lifespan/dependency code) naming the chosen approach (A or
B), the `check_same_thread` value, the locking strategy, and the lifecycle hook.
If you cannot resolve the thread-safety question with confidence, **STOP and
report** — do not ship a guess. No code from Steps 2–4 may land until this
decision exists.

### Step 2: initialize schema once at startup and expose a shared DB dependency

In `dashboard/backend/main.py`, following the approach chosen in Step 1:

1. Add a FastAPI **lifespan** handler (`@asynccontextmanager` passed as
   `FastAPI(lifespan=...)`) that, on startup, runs `init_schema()` **exactly
   once** and creates the long-lived connection/cache; on shutdown, closes it.
2. Add a dependency function (e.g. `def get_db() -> DB: ...`) that returns the
   shared `DB`/connection (per the chosen model) **without** re-running
   `init_schema()` and **without** opening a new `sqlite3.connect` per call.
3. Replace every `with DB() as db:` block in the endpoints
   (`api_overview` 38–41, `api_jobs` 44–47, `api_board` 50–56, `api_job` 59–65,
   `api_set_state` 68–76, `api_mark_applied` 79–83, `api_prep` 86–96,
   `api_mark_sent` 99–105, `api_cv_download` 114–126) with the injected
   dependency (`db: DB = Depends(get_db)`), preserving each endpoint's exact
   logic and JSON response shape. `api_mark_sent`'s direct `db.conn.execute(...)
   + db.conn.commit()` must keep working under the chosen locking model.
4. Keep `api_brief` and `health` DB-free. Keep the static mount last (134–138).

The key behavioral change: `executescript(schema.sql)` and the `schema.sql` disk
read happen **once per process**, not once per request. The `__future__`,
pydantic-v2, and parameterized-query conventions must be preserved.

**Verify**: `uv run --extra dev pytest` → still `9 passed` (no engine regression).
Then start the server (`uv run uvicorn dashboard.backend.main:app --port 8787`)
and confirm `/api/health` returns `{"ok": true}` and `/api/overview` returns its
normal shape without raising the same-thread error. Stop the server.

### Step 3: add a test proving schema init runs once across N requests

Add a test to `tests/test_engine.py` (or, if it needs FastAPI's `TestClient`,
add it there too — `tests/test_engine.py` is the only test file) that:

- Spins up the app via `fastapi.testclient.TestClient` (which exercises the
  lifespan startup) pointed at a `tmp_path` DB.
- Patches/spies on `DB.init_schema` (or `sqlite3.Connection.executescript`, or
  the `schema.sql` read) with a counter.
- Fires **N ≥ 3** requests across at least two endpoints
  (e.g. `/api/overview`, `/api/board`).
- Asserts the spied `init_schema`/`executescript` was called **exactly once**,
  not once per request.

Model the fixture/structure on the existing `db` fixture
(`tests/test_engine.py:17-19`) and the existing network-free test style. Keep it
network-free.

**Verify**: `uv run --extra dev pytest tests/test_engine.py -k <new_test_name>`
→ the new test passes. Then `uv run --extra dev pytest` → `10 passed` (9 existing
+ 1 new; more if you add several).

### Step 4: confirm the frontend still typechecks and builds

No frontend files change, but the backend serves the built frontend, so confirm
no incidental breakage.

**Verify**:
- `npm --prefix dashboard/frontend run typecheck` → exit 0, no errors.
- `npm --prefix dashboard/frontend run build` → exit 0.

## Test plan

- **New test(s)** in `tests/test_engine.py`:
  - `test_schema_init_runs_once_across_requests` (happy path / the regression
    this plan fixes): N≥3 requests across `/api/overview` + `/api/board` trigger
    `init_schema`/`executescript` **exactly once**.
  - Optional edge case: a mutation endpoint (`/api/jobs/{id}/state`) followed by
    a read still uses the shared connection and does not re-init the schema.
- **Structural pattern to copy**: the `db` fixture at `tests/test_engine.py:17-19`
  and the existing network-free test functions in that file.
- **Verification**: `uv run --extra dev pytest` → all pass, including the new
  test(s) (≥ `10 passed`).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] A written threading decision exists (Step 1): approach A or B,
      `check_same_thread` value, locking strategy, lifecycle hook.
- [ ] `uv run --extra dev pytest` exits 0 and reports `10 passed` or more
      (the 9 originals plus the new schema-init test).
- [ ] The new schema-init test exists in `tests/test_engine.py` and proves
      `init_schema`/`executescript` runs **exactly once** across N≥3 requests.
- [ ] `grep -n "with DB()" dashboard/backend/main.py` returns **no matches**
      (every per-request `with DB()` block was replaced by the shared dependency).
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0.
- [ ] `npm --prefix dashboard/frontend run build` exits 0.
- [ ] `git status` shows only `dashboard/backend/main.py`, `engine/db/models.py`,
      and `tests/test_engine.py` modified — no files outside the in-scope list.
- [ ] `plans/README.md` status row for plan 014 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- **The thread-safety question cannot be resolved with confidence** in Step 1.
  Shipping a shared connection without a sound threading model is worse than the
  current per-request cost — do not guess.
- You observe (in manual testing or CI) the error `SQLite objects created in a
  thread can only be used in that same thread`. The chosen model is wrong; stop
  and reconsider the approach rather than papering over it.
- Implementing the shared connection appears to require changing
  `DB.__init__`/`init_schema()` semantics in a way that breaks the standalone
  CLI `with DB() as db:` contract (an out-of-scope caller).
- The code at the locations in "Current state" doesn't match the excerpts
  (`dashboard/backend/main.py:33-138` or `engine/db/models.py:33-49`) — i.e. the
  codebase drifted since commit `c3e2679`.
- A bare `pytest` was run by mistake and reported 2 failures — re-run via
  `uv run --extra dev pytest` (expected `9 passed` baseline) before judging.
- Any step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (`schema.sql`, the
  CLI, the frontend, or any endpoint's public response shape).

## Maintenance notes

For the human/agent who owns this code after the change lands:

- **Concurrency model is the thing to scrutinize in review.** If the app ever
  moves off single-user localhost, runs multiple uvicorn workers, or adds
  `async def` endpoints, the shared-connection assumption (especially approach A's
  single lock / single writer) must be revisited.
- If new sync endpoints are added, they must use the `get_db` dependency, not a
  fresh `with DB()` — the Done-criteria grep guards this only at landing time.
- `api_mark_sent` writes via `db.conn` directly; any future direct-`conn` access
  must go through the same locking discipline as the chosen model.
- **Deferred out of this plan** (and why): connection pooling beyond a single
  shared connection / per-thread cache, and any write-batching, are out of
  scope — this plan only removes the per-request schema re-init and disk read.
  The schema itself stays in `schema.sql` and is left untouched on purpose.
