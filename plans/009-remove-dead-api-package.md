# Plan 009: Remove the empty, unreferenced dashboard/backend/api package

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- dashboard/backend/api dashboard/backend/main.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

`dashboard/backend/api/` contains exactly one file, `__init__.py`, which is
0 bytes. Nothing in the repo imports `dashboard.backend.api` — every route
lives in `dashboard/backend/main.py`, which imports from `engine.*` directly.
The empty package is dead scaffolding (finding TECHDEBT-02, HIGH): it falsely
implies an API layer exists under `api/`, sending a reader looking for route
definitions to an empty directory instead of `main.py`. Deleting it removes a
misleading signal at zero behavioral cost. After this lands, the backend
package contains only the files that actually run.

## Current state

Relevant paths:

- `dashboard/backend/api/__init__.py` — the only file in `dashboard/backend/api/`; 0 bytes (confirmed via `wc -c` → `0`). No code, no consumers.
- `dashboard/backend/main.py` — the real backend: a FastAPI app whose routes import from `engine.*`. This file is the reason `api/` is provably unused.

The imports in `main.py` go straight to `engine`, never to `backend.api` (`dashboard/backend/main.py:17-22`):

```python
from engine import analytics
from engine.db.models import DB
from engine.normalize import STATES, now_iso
from engine.paths import OUTBOX_DIR, REPO_ROOT

app = FastAPI(title="Atlas", docs_url="/api/docs")
```

The only `mount`/`StaticFiles` use serves the built frontend dist, not anything from `api/` (`dashboard/backend/main.py:134-138`):

```python
# ── Serve the built frontend (if present) ────────────────────────────────────
# Mounted LAST so it never shadows the /api/* routes.
_DIST = REPO_ROOT / "dashboard" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
```

Note: the `/api/*` strings in `main.py` are URL route paths (e.g. `@app.get("/api/overview")`), NOT references to the `dashboard.backend.api` Python package. Do not confuse them.

Confirmation that no Python module references the package (ran at plan time, returned no matches):

```
$ grep -rn "backend\.api\|from dashboard.backend.api" dashboard engine brain
# (no output)
```

Repo conventions that apply (match them; nothing in this plan adds code, but the executor must not introduce drift): Python 3.11+ across `engine/`, `brain/`, `dashboard/backend/`; `from __future__ import annotations` at the top of modules; typer CLI; pydantic v2 models; `rich.console` for output; `sqlite3` with PARAMETERIZED queries + WAL; `@dataclass` result objects; sha1 16-char natural keys; UPSERT + COALESCE gap-fill. Tests live in `tests/test_engine.py`. This plan deletes a directory only — it writes no new code and adds no new test, so these conventions are listed for context, not for changes.

## Commands you will need

| Purpose            | Command                                              | Expected on success                |
|--------------------|------------------------------------------------------|------------------------------------|
| Confirm 0 bytes    | `wc -c dashboard/backend/api/__init__.py`            | `0 dashboard/backend/api/__init__.py` |
| Confirm no consumers | `grep -rn "backend\.api\|from dashboard.backend.api" dashboard engine brain` | no output, exit 1 |
| App still imports  | `uv run python -c "import dashboard.backend.main"`   | exit 0, no traceback               |
| Python tests       | `uv run --extra dev pytest`                          | `9 passed`                         |
| Working tree state | `git status`                                         | only `dashboard/backend/api/` deleted |

Do NOT run bare `pytest`: the global interpreter is missing `docx`, `rapidfuzz`, and `reportlab`, so it falsely fails 2 tests. Always use `uv run --extra dev pytest`.

## Scope

**In scope** (the only path you should modify):
- `dashboard/backend/api/` — delete the entire directory (its only content is the 0-byte `__init__.py`).

**Out of scope** (do NOT touch, even though they look related):
- `dashboard/backend/main.py` — the real backend; it never imports `api/`, so it needs no edit. Do not "clean up" its `/api/*` route strings.
- Any other file under `dashboard/`, `engine/`, `brain/`, or `tests/`.

## Git workflow

- Branch: `advisor/009-remove-dead-api-package` (based on the latest `master`).
- Commit the single deletion; message style matches the repo's plain imperative summaries (see `git log`, e.g. `Add one-command dashboard launcher (scripts/run.sh)`). Suggested message: `Remove empty, unreferenced dashboard/backend/api package`.
- Stage only the deleted path by name (`git add dashboard/backend/api/__init__.py` / `git rm`). Never `git add .` or `git add -A`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Re-confirm the package is empty and unreferenced

Before deleting, verify the two facts this plan rests on.

Run:
```
wc -c dashboard/backend/api/__init__.py
grep -rn "backend\.api\|from dashboard.backend.api" dashboard engine brain
```

**Verify**: first command prints `0 dashboard/backend/api/__init__.py`; second command prints nothing (exit status 1). If `__init__.py` is non-zero or the grep returns any match, this is a STOP condition.

### Step 2: Delete the directory

Remove the entire `dashboard/backend/api/` directory:
```
git rm -r dashboard/backend/api
```
(If the file is untracked for some reason, use `rm -rf dashboard/backend/api` instead, then stage the removal.)

**Verify**: `test ! -e dashboard/backend/api && echo gone` → prints `gone`.

### Step 3: Confirm the app still imports

The deletion must not break the FastAPI app's import graph.
```
uv run python -c "import dashboard.backend.main"
```

**Verify**: exit 0, no traceback printed.

### Step 4: Confirm the test suite is unchanged

```
uv run --extra dev pytest
```

**Verify**: output ends with `9 passed` (same count as before this plan).

## Test plan

No new tests. This plan deletes dead scaffolding with no behavior; it is covered by the existing suite (`tests/test_engine.py`) plus the import smoke check.

- Regression guard: `uv run python -c "import dashboard.backend.main"` exits 0 — proves the deleted package was not on any import path.
- Suite unchanged: `uv run --extra dev pytest` → `9 passed`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `test ! -e dashboard/backend/api && echo gone` prints `gone` (directory removed)
- [ ] `uv run python -c "import dashboard.backend.main"` exits 0
- [ ] `uv run --extra dev pytest` exits 0 and reports `9 passed`
- [ ] `grep -rn "backend\.api\|from dashboard.backend.api" dashboard engine brain` returns no matches
- [ ] `git status` shows only `dashboard/backend/api/__init__.py` deleted — no other file modified
- [ ] `plans/README.md` status row for plan 009 updated

## STOP conditions

Stop and report back (do not improvise) if:

- `dashboard/backend/api/__init__.py` is NOT 0 bytes, or `dashboard/backend/api/` contains files other than `__init__.py` (the package is no longer empty — it may have gained real code since this plan was written).
- `grep -rn "backend\.api\|from dashboard.backend.api" dashboard engine brain` returns ANY match (something now imports the package; deleting it would break that import).
- `uv run python -c "import dashboard.backend.main"` fails after the deletion.
- `uv run --extra dev pytest` does not report `9 passed` (count changed, or new failures appear).
- The drift check shows `dashboard/backend/main.py` changed since `c3e2679` and its current `:17-22` / `:134-138` no longer match the excerpts in "Current state".

## Maintenance notes

For the human/agent who owns this code after the change lands:

- If a future change introduces a real API layer split out of `main.py`, recreate the package deliberately with actual route modules — do not resurrect an empty `__init__.py`.
- A reviewer should confirm the PR is a pure deletion: only `dashboard/backend/api/__init__.py` removed, no edits to `main.py` or any route strings.
- No follow-up deferred; this plan is self-contained.
