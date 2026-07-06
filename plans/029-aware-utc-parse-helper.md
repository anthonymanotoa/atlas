# Plan 029: One shared aware-UTC datetime parser (kill the three copies of the naive-tzinfo guard)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 0ed8967..HEAD -- engine/normalize.py engine/analytics.py engine/outreach/followups.py tests/test_f3_followups_v2.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `0ed8967`, 2026-07-06

## Why this matters

Three places parse ISO timestamps from SQLite and each independently re-implements the same
"naive → assume UTC" normalization: `analytics._days_since`, and two call sites in
`engine/outreach/followups.py` (`seed_for_state`, `bucket_followups`). Meanwhile
`followups._parse` — the function that SHOULD own this — returns a **naive** datetime when fed a
naive string, forcing every caller to re-guard; and one caller (`schedule`, line 34) applies no
guard at all, so it stores a naive `due_at` whenever it receives a naive `base_iso` (harmless
today only because readers re-normalize). No live bug was found — this is convergence-before-
divergence: make `_parse` always return aware-UTC via one shared helper in `engine/normalize.py`,
delete the per-site guards, and future datetime code has one obvious correct primitive.

## Current state

- `engine/outreach/followups.py:20-24` — the parser that returns naive datetimes:

  ```python
  def _parse(iso: str) -> datetime:
      try:
          return datetime.fromisoformat(iso)
      except ValueError:
          return datetime.now(UTC)
  ```

- `engine/outreach/followups.py:34` (inside `schedule()`) — unguarded use:

  ```python
  base = _parse(base_iso) if base_iso else datetime.now(UTC)
  ```

- `engine/outreach/followups.py:129-131` (inside `seed_for_state()`) — guarded use:

  ```python
  base = _parse(base_iso) if base_iso else datetime.now(UTC)
  if base.tzinfo is None:
      base = base.replace(tzinfo=UTC)
  ```

- `engine/outreach/followups.py:156-158` (inside `bucket_followups()`) — guarded use:

  ```python
  due = _parse(f.get("due_at") or "")
  if due.tzinfo is None:
      due = due.replace(tzinfo=UTC)
  ```

- `engine/analytics.py:30-42` — the sibling implementation (note it ALSO handles bare
  `YYYY-MM-DD` and returns `None` on garbage instead of `now`):

  ```python
  def _days_since(iso: str | None) -> float | None:
      if not iso:
          return None
      try:
          dt = datetime.fromisoformat(iso)
      except (ValueError, TypeError):
          try:  # bare 'YYYY-MM-DD' (e.g. date_posted) — fromisoformat handles it on 3.11+, but be safe
              dt = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
          except (ValueError, TypeError):
              return None
      if dt.tzinfo is None:  # naive (bare date) → assume UTC so the subtraction is aware-safe
          dt = dt.replace(tzinfo=UTC)
      return round((datetime.now(UTC) - dt).total_seconds() / 86400, 1)
  ```

- `engine/normalize.py` — the natural home for the shared helper: already
  `from datetime import UTC, datetime` (line 7) and hosts `now_iso()` at line 55.
- Conventions: `from __future__ import annotations`; follow-up tests live in
  `tests/test_f3_followups_v2.py` (model new tests on it); analytics tests in
  `tests/test_f3_analytics.py`.

## Commands you will need

| Purpose      | Command                                              | Expected on success |
|--------------|------------------------------------------------------|---------------------|
| Sync deps    | `uv sync`                                            | exit 0              |
| Python tests | `uv run pytest`                                      | exit 0, all pass    |
| Focused      | `uv run pytest tests/test_f3_followups_v2.py tests/test_f3_analytics.py -q` | all pass |
| Lint         | `uv run ruff check . && uv run ruff format --check .`| exit 0              |

## Scope

**In scope** (the only files you should modify):
- `engine/normalize.py` (add the helper)
- `engine/outreach/followups.py`
- `engine/analytics.py`
- `tests/test_f3_followups_v2.py` (new tests)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch, even though they look related):
- How timestamps are WRITTEN (`now_iso()`, `due_at` storage format) — readers-side change only.
- `engine/reposts.py`, `engine/discovery/liveness.py` or any other module's date handling —
  audit found no naive/aware mixing there; do not refactor speculatively.
- `bucket_followups`'s explicit `now` parameter design (deliberate, for test determinism).

## Git workflow

- Branch: current session branch; conventional commit, e.g.
  `refactor(time): shared aware-UTC ISO parser in normalize; followups/_days_since use it`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add `parse_dt_utc` to `engine/normalize.py`

Near `now_iso()` (line ~55), add:

```python
def parse_dt_utc(iso: str | None) -> datetime | None:
    """Parse an ISO-8601 string (or bare YYYY-MM-DD) into an AWARE UTC datetime.

    Naive inputs are assumed UTC (SQLite rows written by now_iso() are aware, but legacy/
    bare-date values exist). Returns None on garbage — callers pick their own fallback.
    """
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso))
    except (ValueError, TypeError):
        try:
            dt = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
```

**Verify**: `uv run python -c "from engine.normalize import parse_dt_utc; from datetime import UTC; d=parse_dt_utc('2026-01-15'); assert d and d.tzinfo is not None; assert parse_dt_utc('garbage') is None; print('ok')"` → `ok`

### Step 2: Route `followups._parse` through it

In `engine/outreach/followups.py`:

```python
from engine.normalize import parse_dt_utc

def _parse(iso: str) -> datetime:
    return parse_dt_utc(iso) or datetime.now(UTC)
```

(Keeps `_parse`'s existing "garbage → now" fallback contract so `schedule()`'s behavior is
unchanged for bad input.) Then DELETE the now-redundant guards:
- `seed_for_state`: remove the two lines `if base.tzinfo is None: base = base.replace(tzinfo=UTC)`.
- `bucket_followups`: remove the two lines `if due.tzinfo is None: due = due.replace(tzinfo=UTC)`.

**Verify**: `grep -n "tzinfo is None" engine/outreach/followups.py` → 0 matches.
**Verify**: `uv run pytest tests/test_f3_followups_v2.py -q` → all pass.

### Step 3: Route `analytics._days_since` through it

In `engine/analytics.py`, reimplement the body of `_days_since` (keep its exact signature and
return contract — `None` on garbage, rounded float otherwise):

```python
from engine.normalize import parse_dt_utc

def _days_since(iso: str | None) -> float | None:
    dt = parse_dt_utc(iso)
    if dt is None:
        return None
    return round((datetime.now(UTC) - dt).total_seconds() / 86400, 1)
```

(Check `engine/analytics.py`'s existing imports before adding; it may already import from
`engine.normalize`.)

**Verify**: `uv run pytest tests/test_f3_analytics.py -q` → all pass.
**Verify**: `grep -n "tzinfo is None" engine/analytics.py` → 0 matches.

### Step 4: Pin the naive-input behavior with tests

In `tests/test_f3_followups_v2.py`, add (match the file's existing style and fixtures):

1. `test_schedule_stores_aware_due_at_for_naive_base` — call `schedule(db, job_id,
   channel="email", base_iso="2026-01-15T10:00:00")` (naive) and assert every created
   followup's `due_at` parses to an AWARE datetime
   (`datetime.fromisoformat(f["due_at"]).tzinfo is not None`).
2. `test_bucket_followups_naive_due_at_still_buckets` — feed `bucket_followups` a pending row
   whose `due_at` is `"2026-01-01"` (bare date) with an aware `now`, assert it lands in
   `overdue` and no exception is raised (this pins the legacy-naive-rows path the deleted
   guards used to cover).

**Verify**: `uv run pytest tests/test_f3_followups_v2.py -q` → all pass, including 2 new tests.

### Step 5: Full gate + index row

**Verify**: `uv run pytest` → exit 0.
**Verify**: `uv run ruff check . && uv run ruff format --check .` → exit 0.
**Verify**: `git status --short` → only in-scope files modified.
Update this plan's row in `plans/README.md` to DONE.

## Test plan

- The 2 new tests in step 4 (naive `base_iso` → aware `due_at`; bare-date `due_at` still buckets).
- Existing suites `tests/test_f3_followups_v2.py` + `tests/test_f3_analytics.py` are the
  regression net for the refactor.
- Verification: `uv run pytest` → all pass, 2 new tests included.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -rn "tzinfo is None" engine/outreach/followups.py engine/analytics.py` → 0 matches
- [ ] `grep -n "def parse_dt_utc" engine/normalize.py` → 1 match
- [ ] `uv run pytest` exits 0; the 2 new tests exist and pass
- [ ] `uv run ruff check .` and `uv run ruff format --check .` exit 0
- [ ] `git status --short` shows only in-scope files modified
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The excerpts in "Current state" don't match the live code (drift).
- Any EXISTING test fails after step 2 or 3 — the guards you deleted were covering behavior
  the plan didn't predict; report the failing test, do not paper over it.
- You find other modules importing `followups._parse` or `analytics._days_since` directly
  (grep first: `grep -rn "_days_since\|followups._parse" engine/ dashboard/ brain/`) beyond
  their home modules — the plan assumed they're module-private.

## Maintenance notes

- New code that parses stored timestamps should use `normalize.parse_dt_utc` — reviewers should
  flag any fresh `datetime.fromisoformat` + tzinfo-guard pattern in review.
- If timestamp WRITES are ever normalized (all writers guaranteed aware), `parse_dt_utc`'s
  naive branch becomes dead but harmless — leave it.
