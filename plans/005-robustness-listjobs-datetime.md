# Plan 005: Harden `list_jobs` against generators + date-diff against naive datetimes

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- engine/db/models.py engine/analytics.py engine/heartbeat.py tests/test_engine.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

Two latent bugs that do not surface in the current test suite but will crash at
runtime under inputs the code already advertises as legal.

- **Finding A (CORRECTNESS-05)** — `DB.list_jobs` accepts `states: Optional[Iterable[str]]`.
  Its implementation iterates `states` twice: once to count placeholders (via
  `len(list(states))`) and once to bind params (`params.extend(states)`). If a
  caller passes a one-shot iterable (a generator, `map`, `filter`, `zip`, a
  consumed `dict.keys()` view in some cases), the first pass exhausts it, so the
  SQL gets N `?` placeholders but 0 bound parameters → `sqlite3.ProgrammingError`.
  A list happens to work today, which is why no test caught it — but the
  signature promises any `Iterable`.

- **Finding B (CORRECTNESS-06)** — `analytics._days_since` and the heartbeat
  freshness helpers subtract an aware "now" (`datetime.now(timezone.utc)`) from a
  value parsed with `datetime.fromisoformat`. If the stored ISO string is
  *naive* (no offset — e.g. a value written before timezone stamping, an external
  import, or a hand-edited DB), the subtraction raises `TypeError: can't subtract
  offset-naive and offset-aware datetimes`. The code only catches `ValueError`,
  so the `TypeError` escapes and takes down `/api/overview` instead of degrading
  to `None` (the intended "unknown / skip" sentinel).

When this lands, both functions degrade gracefully instead of throwing, and a
regression test pins the generator contract for `list_jobs`.

## Current state

Relevant files:

- `engine/db/models.py` — SQLite access layer; `list_jobs` query builder (lines 113–127) has the double-iteration bug. `from __future__ import annotations` is present (line 11) and `Iterable` is already imported and used in the signature.
- `engine/analytics.py` — dashboard analytics; `_days_since` (lines 25–31) is the naive/aware subtraction site that backs `/api/overview`.
- `engine/heartbeat.py` — freshness heartbeat; `last_success` parse (lines 26–29) and `downtime_hours` subtraction (line 37) are the second naive/aware site.
- `tests/test_engine.py` — the engine's unit tests (network-free); new regression test goes here.

### `engine/db/models.py:113-127` (the bug)

```python
    def list_jobs(self, state: Optional[str] = None, states: Optional[Iterable[str]] = None,
                  limit: Optional[int] = None) -> list[dict]:
        q, params = "SELECT * FROM jobs", []
        clauses = []
        if state:
            clauses.append("state=?"); params.append(state)
        if states:
            placeholders = ",".join("?" * len(list(states)))
            clauses.append(f"state IN ({placeholders})"); params.extend(states)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY COALESCE(fit_score,-1) DESC, discovered_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        return [dict(r) for r in self.conn.execute(q, params).fetchall()]
```

Note: `if states:` truthiness-tests the iterable. A generator object is always
truthy even when empty, so materializing first (Step 1) also keeps the empty
case from emitting a malformed `state IN ()` only if guarded — see Step 1 for
the exact target shape.

### `engine/analytics.py:25-31` (Finding B, site 1)

```python
def _days_since(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        return round((datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 86400, 1)
    except ValueError:
        return None
```

`datetime` and `timezone` are imported at `engine/analytics.py:5`
(`from datetime import datetime, timezone`).

### `engine/heartbeat.py:22-38` (Finding B, site 2)

```python
def last_success(db: DB) -> Optional[datetime]:
    raw = db.meta_get("last_success_ts")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def downtime_hours(db: DB) -> Optional[float]:
    """Hours since last success if it exceeds STALE_HOURS, else None."""
    ls = last_success(db)
    if not ls:
        return None
    gap = (datetime.now(timezone.utc) - ls).total_seconds() / 3600
    return round(gap, 1) if gap > STALE_HOURS else None
```

`datetime` and `timezone` are imported at `engine/heartbeat.py:9`
(`from datetime import datetime, timezone`). The `TypeError` here can be raised
by the subtraction in `downtime_hours` (line 37) when `last_success` returns a
*naive* datetime parsed at line 27. Guarding the parse alone is not enough — the
subtraction at line 37 must also be protected (see Step 3).

### Existing test pattern to match — `tests/test_engine.py:36-44`

```python
def test_upsert_idempotent_and_gapfills(db: DB):
    j1 = Job(source="greenhouse", title="Data Scientist", company="Acme Inc", location="Remote")
    assert db.upsert_job(j1) is True
    j2 = Job(source="indeed", title="Data Scientist", company="Acme",
             location="Remote", description="Full description here")
    assert db.upsert_job(j2) is False                      # same natural key → not created
    row = db.get_job(j1.finalize().id)
    assert row["description"] == "Full description here"   # gap-filled
    assert len(db.list_jobs()) == 1                        # no duplicate
```

The new test uses the same `db` fixture (`tests/test_engine.py:16-18`, a
`tmp_path`-backed `DB`) and the same `Job(...)` / `db.upsert_job(...)`
construction style. Imports already present at the top of the file:
`from engine.db.models import DB` and `from engine.normalize import Job, compute_job_id`.

### Conventions this plan honors (match them)

- `from __future__ import annotations` at the top of every module (present in all three source files).
- pydantic v2 models / `@dataclass` results elsewhere — not touched here.
- sqlite3 **parameterized** queries (the fix preserves placeholder binding; do not interpolate states into the SQL string).
- Tests are network-free and live in `tests/test_engine.py`; model new tests after the functions there.
- typer CLI / rich.console — not touched here.

## Commands you will need

| Purpose            | Command                                          | Expected on success            |
|--------------------|--------------------------------------------------|--------------------------------|
| Python tests       | `uv run --extra dev pytest`                      | exit 0, `10 passed` (was 9 + 1 new) |
| Run one new test   | `uv run --extra dev pytest -k list_jobs_generator` | exit 0, `1 passed`           |
| Drift check        | `git diff --stat c3e2679..HEAD -- engine/db/models.py engine/analytics.py engine/heartbeat.py tests/test_engine.py` | only in-scope files |
| Confirm scope      | `git status --porcelain`                         | only in-scope files listed     |

> Do NOT run bare `pytest`. The global interpreter is missing `docx`,
> `rapidfuzz`, and `reportlab`, so bare `pytest` falsely fails 2 tests. Always
> use `uv run --extra dev pytest`, which today reports `9 passed` before this
> change and must report `10 passed` after.

## Scope

**In scope** (the only files you may modify):
- `engine/db/models.py` — fix `list_jobs` double-iteration (Step 1)
- `engine/analytics.py` — widen `_days_since` except clause (Step 2)
- `engine/heartbeat.py` — widen `last_success` parse + protect `downtime_hours` subtraction (Step 3)
- `tests/test_engine.py` — add the generator regression test (Step 4)

**Out of scope** (do NOT touch):
- The `list_jobs` SQL shape, ordering, or `limit` handling beyond the iteration fix.
- The `state=?` single-state branch — it is correct and unaffected.
- Any caller of `list_jobs` / `_days_since` / `downtime_hours` — the fix is internal; signatures and return contracts are unchanged.
- The dashboard backend (`dashboard/backend/`) and frontend — no API shape changes, so no frontend work is required.
- Any new dependency. The fix is pure stdlib.

## Git workflow

- Branch: `advisor/005-robustness-listjobs-datetime` (created from latest `master`).
- Commit per logical unit; one commit for the two guards + the regression test is acceptable. Message style matches the repo's terse imperative log (e.g. recent commit `5b0f1a3 advisor: surface [confirma] gaps in CV audit`).
- Stage only the in-scope files **by name** (`git add engine/db/models.py engine/analytics.py engine/heartbeat.py tests/test_engine.py`). Never `git add .` / `git add -A`.
- Do NOT push or open a PR.

## Steps

### Step 1: Materialize `states` once in `list_jobs`

In `engine/db/models.py`, replace the `if states:` block so the iterable is
converted to a list exactly once and both the placeholders and the params derive
from that same list. Also guard the empty case so an empty iterable does not
emit a malformed `state IN ()`.

Target shape for the block at lines 119–121:

```python
        if states:
            states = list(states)
            if states:
                placeholders = ",".join("?" * len(states))
                clauses.append(f"state IN ({placeholders})"); params.extend(states)
```

Rationale: `list(states)` is computed once; `len(states)` and `params.extend(states)`
now operate on the materialized list, so a generator yields matching placeholder
and param counts. The inner `if states:` skips the clause when the iterable was
empty (an empty generator is truthy on the outer check but yields `[]`).

**Verify**: `uv run --extra dev pytest -k list_jobs_generator` → `1 passed`
(after Step 4 adds the test). For now confirm the module still imports:
`uv run --extra dev python -c "import engine.db.models"` → exit 0, no output.

### Step 2: Catch `TypeError` in `_days_since`

In `engine/analytics.py`, widen the except clause at line 30 from `except ValueError:`
to `except (ValueError, TypeError):`. No other line changes.

Resulting block:

```python
def _days_since(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        return round((datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 86400, 1)
    except (ValueError, TypeError):
        return None
```

**Verify**: `uv run --extra dev python -c "from engine.analytics import _days_since; print(_days_since('2026-06-01T00:00:00'))"` → prints a float (e.g. `12.0`), exit 0.

### Step 3: Catch `TypeError` in the heartbeat freshness path

In `engine/heartbeat.py`, two changes:

1. `last_success` (line 28): widen `except ValueError:` to `except (ValueError, TypeError):`.
2. `downtime_hours` (line 37): the subtraction `datetime.now(timezone.utc) - ls`
   can raise `TypeError` when `ls` is naive. Wrap it so it degrades to `None`.

Target shape for `downtime_hours`:

```python
def downtime_hours(db: DB) -> Optional[float]:
    """Hours since last success if it exceeds STALE_HOURS, else None."""
    ls = last_success(db)
    if not ls:
        return None
    try:
        gap = (datetime.now(timezone.utc) - ls).total_seconds() / 3600
    except TypeError:
        return None
    return round(gap, 1) if gap > STALE_HOURS else None
```

**Verify**: `uv run --extra dev python -c "import engine.heartbeat"` → exit 0, no output.

### Step 4: Add the generator regression test

In `tests/test_engine.py`, add a test that passes a **generator** (one-shot
iterable) to `list_jobs(states=...)` and asserts it returns rows without raising.
Model it on `test_upsert_idempotent_and_gapfills` (use the `db` fixture and
`Job`/`upsert_job`). Insert a job, advance/leave it in a known state, then query
with a generator over candidate states.

Suggested test (adapt state values to whatever `Job` lands in on insert — a
freshly upserted job is in `discovered`):

```python
def test_list_jobs_generator_states_no_programming_error(db: DB):
    j = Job(source="greenhouse", title="Data Scientist", company="Acme", location="Remote")
    db.upsert_job(j)
    # A generator is a one-shot iterable; the old code consumed it counting
    # placeholders, leaving zero params bound -> sqlite3.ProgrammingError.
    states = (s for s in ("discovered", "scored"))
    rows = db.list_jobs(states=states)
    assert len(rows) == 1
    assert rows[0]["state"] == "discovered"
```

If a freshly upserted job is not in `state == "discovered"`, STOP and report —
do not guess the state machine; the rest of the plan does not depend on the
exact value, only on the generator not raising. (A minimal fallback assertion is
`assert isinstance(rows, list)`.)

**Verify**: `uv run --extra dev pytest -k list_jobs_generator` → `1 passed`.

## Test plan

- New test in `tests/test_engine.py`: `test_list_jobs_generator_states_no_programming_error`
  — passes a generator to `list_jobs(states=...)` and asserts rows are returned
  with no `sqlite3.ProgrammingError`. This is the regression for Finding A.
- Structural pattern: model after `tests/test_engine.py:36` (`test_upsert_idempotent_and_gapfills`) — same `db` fixture, same `Job(...)` + `db.upsert_job(...)` style.
- Finding B has no new dedicated test (the guard is a defensive widening; the
  existing suite plus the import smoke-checks in Steps 2–3 cover it). If you want
  belt-and-suspenders, an optional unit test calling `_days_since` on a naive ISO
  string and asserting `None` is acceptable but not required.
- Verification: `uv run --extra dev pytest` → exit 0, `10 passed` (the prior 9 plus 1 new).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports `10 passed`.
- [ ] `uv run --extra dev pytest -k list_jobs_generator` exits 0, `1 passed`.
- [ ] `grep -n "len(list(states))" engine/db/models.py` returns no matches (old double-iteration gone).
- [ ] `grep -n "except (ValueError, TypeError)" engine/analytics.py` returns 1 match.
- [ ] `grep -n "except (ValueError, TypeError)" engine/heartbeat.py` returns 1 match.
- [ ] `grep -n "except TypeError" engine/heartbeat.py` returns 1 match (the `downtime_hours` guard).
- [ ] `git status --porcelain` lists only the four in-scope files.
- [ ] `plans/README.md` status row for 005 updated to DONE.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at any location in "Current state" does not match the quoted excerpts
  (the codebase drifted since commit `c3e2679`) — especially if `list_jobs` no
  longer contains `len(list(states))`, or the except clauses already include
  `TypeError`.
- `uv run --extra dev pytest` does not report `9 passed` *before* your changes
  (baseline mismatch — something else is broken; do not stack your change on it).
- A freshly upserted `Job` is not in `state == "discovered"`, so the Step 4
  assertion `rows[0]["state"] == "discovered"` cannot hold — report the actual
  state rather than guessing.
- The fix appears to require touching a caller of `list_jobs`, `_days_since`, or
  `downtime_hours`, or any file outside the in-scope list.
- Any verification fails twice after a reasonable fix attempt.

## Maintenance notes

For whoever owns this code next:

- `list_jobs` now tolerates any `Iterable[str]` for `states`, including one-shot
  iterables. If the signature is ever narrowed back to `list[str]`, the inner
  re-materialization is harmless but redundant.
- The `(ValueError, TypeError)` widening is a deliberate "degrade to None"
  contract: callers treat `None` from `_days_since` / `downtime_hours` /
  `last_success` as "unknown / skip". Do not change these to re-raise without
  auditing `/api/overview` and the dashboard freshness banner that consume them.
- Root cause of Finding B is mixed naive/aware timestamps in the DB. A cleaner
  long-term fix is to normalize all stored timestamps to aware UTC at write time
  (see `engine/normalize.now_iso`) so the subtraction can never see a naive value
  — explicitly deferred out of this plan to keep it low-risk and storage-stable.
- Reviewer should scrutinize: that the SQL stays parameterized (no state values
  interpolated into the query string), and that the empty-iterable case does not
  emit `state IN ()`.
