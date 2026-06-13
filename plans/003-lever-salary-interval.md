# Plan 003: Lever salary intervals normalized so fit scoring annualizes correctly

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- engine/discovery/ats/lever.py engine/scoring/fit.py tests/test_engine.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

Lever's ATS emits salary interval strings shaped like `per-year-salary`,
`per-month-salary`, and `per-hour-wage`. The Lever adapter only strips the
`per-` prefix, leaving values like `year-salary` / `month-salary` /
`hour-wage`. The fit scorer's annualization lookup keys on exactly `hourly` /
`monthly` / `yearly`, so none of the Lever strings match and every Lever salary
is treated as already-annual (multiplier 1). The concrete cost: a monthly or
hourly figure is compared directly against a USD annual floor, so genuinely
well-paid monthly/hourly Lever roles get tagged "salary below floor" (and, if
`salary_hard` is set, disqualified) while the same role from another ATS scores
correctly. After this lands, the adapter emits canonical interval names and the
scorer annualizes Lever salaries the same way it does for every other source.

## Current state

Files involved:

- `engine/discovery/ats/lever.py` — Lever ATS adapter; builds the normalized
  job record. The salary-interval mapping bug is on line 46.
- `engine/scoring/fit.py` — fit scorer; the salary component (annualization +
  floor check) is at lines 89–104.
- `tests/test_engine.py` — existing unit tests; new regression test goes here,
  modeled on the tests already in this file.

Current code, `engine/discovery/ats/lever.py:42-49`:

```python
            employment_type=cats.get("commitment"),
            salary_min=to_float(sal.get("min")),
            salary_max=to_float(sal.get("max")),
            salary_currency=sal.get("currency"),
            salary_interval=(sal.get("interval") or "").replace("per-", "") or None,
            date_posted=None,
            raw={"team": cats.get("team"), "country": p.get("country")},
        ))
```

The `.replace("per-", "")` on line 46 turns `per-year-salary` into
`year-salary` (and `per-month-salary` → `month-salary`, `per-hour-wage` →
`hour-wage`). It never produces the canonical `yearly` / `monthly` / `hourly`.

Current code, `engine/scoring/fit.py:89-104`:

```python
    # 4. Salary (soft unless criteria.salary_hard).
    smin, smax = job.get("salary_min"), job.get("salary_max")
    floor = criteria.salary_floor_usd
    if floor and (smin or smax):
        top = smax or smin
        interval = (job.get("salary_interval") or "yearly").lower()
        annual = top * {"hourly": 2080, "monthly": 12, "yearly": 1}.get(interval, 1)
        if annual >= floor:
            score += 10
            reasons.append("salary meets floor")
        else:
            if criteria.salary_hard:
                disq = True
            score -= 10
            reasons.append("salary below floor")
```

The lookup `{"hourly": 2080, "monthly": 12, "yearly": 1}.get(interval, 1)` on
line 95 defaults to multiplier `1` for any non-matching key, so `month-salary`
and `hour-wage` both fall through to "treat as yearly".

Repo conventions that apply here (match them):

- Module headers start with `from __future__ import annotations`.
- Pydantic v2 models, `@dataclass` for result objects, typer CLI, `rich.console`
  for output — none of those are touched by this change, but keep the
  module style consistent.
- New tests are written in `tests/test_engine.py`, modeled structurally on the
  tests already in that file (plain `def test_*` functions, direct asserts on
  the scorer/adapter return values). Run tests with the project's verify
  command below — never bare `pytest`.

## Commands you will need

| Purpose            | Command                                          | Expected on success            |
|--------------------|--------------------------------------------------|--------------------------------|
| Python tests       | `uv run --extra dev pytest`                      | exit 0, "9 passed" → "10 passed" after the new test |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`  | exit 0, no errors              |
| Frontend build     | `npm --prefix dashboard/frontend run build`      | exit 0                         |

Do NOT run bare `pytest`: the global interpreter is missing `docx`,
`rapidfuzz`, and `reportlab`, which falsely fails 2 tests. Always use
`uv run --extra dev pytest`. This change is Python-only; the frontend commands
are listed only as a sanity gate and are expected to be unaffected.

## Scope

**In scope** (the only files you should modify):
- `engine/discovery/ats/lever.py`
- `engine/scoring/fit.py`
- `tests/test_engine.py`

**Out of scope** (do NOT touch, even though they look related):
- Other ATS adapters under `engine/discovery/ats/` — they already emit
  canonical interval strings (`hourly` / `monthly` / `yearly`); reworking them
  is unnecessary and risks regressions in sources that are currently correct.
- Any change to the pydantic job model's `salary_interval` field type or to the
  scorer's point weights / floor semantics — only the interval-string mapping
  and the annualization multiplier table change.

## Git workflow

- Branch: `advisor/003-lever-salary-interval` (off the latest `main`).
- Commit per logical unit; keep the message imperative and scoped to the fix.
- Do NOT push or open a PR — the operator decides when to merge.

## Steps

### Step 1: Add a canonical interval normalizer and use it in the Lever adapter

In `engine/discovery/ats/lever.py`, introduce a small normalizer that maps any
raw interval string to one canonical token by substring match, then use it in
place of the `.replace("per-", "")` on line 46.

Target shape of the normalizer (place it as a module-level helper near the top
of the file, after the imports):

```python
def _norm_interval(raw: str | None) -> str | None:
    s = (raw or "").lower()
    if not s:
        return None
    if "hour" in s:
        return "hourly"
    if "week" in s:
        return "weekly"
    if "month" in s:
        return "monthly"
    if "year" in s or "annum" in s or "annual" in s:
        return "yearly"
    if "day" in s or "daily" in s:
        return "daily"
    return None
```

Then replace line 46 so it reads:

```python
            salary_interval=_norm_interval(sal.get("interval")),
```

This maps `per-year-salary` → `yearly`, `per-month-salary` → `monthly`,
`per-hour-wage` → `hourly`, and returns `None` for empty/unknown input
(preserving the old `... or None` behavior).

**Verify**: `uv run --extra dev pytest` → exit 0, "9 passed" (no regression
yet; the new test is added in Step 3).

### Step 2: Extend the fit scorer's multiplier table and make the lookup tolerant

In `engine/scoring/fit.py`, extend the annualization map on line 95 to include
`weekly` (52) and `daily` (260), keeping the existing `hourly` (2080),
`monthly` (12), `yearly` (1). The lookup already lowercases the interval and
defaults to `1`; keep that default so an unrecognized interval still degrades
gracefully to "treat as yearly".

Target shape (replacing line 95):

```python
        annual = top * {
            "hourly": 2080,
            "daily": 260,
            "weekly": 52,
            "monthly": 12,
            "yearly": 1,
        }.get(interval, 1)
```

Because Step 1 now feeds the scorer canonical tokens, `monthly` resolves to
multiplier 12 and `hourly` to 2080 for Lever jobs, matching every other source.

**Verify**: `uv run --extra dev pytest` → exit 0, "9 passed".

### Step 3: Add a regression test for a Lever-style monthly salary above the floor

In `tests/test_engine.py`, add a test (modeled on the existing tests in that
file) that constructs a job dict as the Lever adapter would emit it after
Step 1 — `salary_interval="monthly"` — with a monthly figure that annualizes
above the criteria floor, and asserts the scorer records "salary meets floor"
and NOT "salary below floor".

Pick values where the bug would have failed: e.g. `salary_max=10000`,
`salary_interval="monthly"` against `salary_floor_usd=100000`. Pre-fix this
annualized to `10000` (below floor → "salary below floor"); post-fix it
annualizes to `120000` (≥ floor → "salary meets floor").

Assert on the scorer's returned reasons list (match how the existing tests in
`tests/test_engine.py` inspect the scoring result — use the same accessor those
tests use; do not invent a new API). The two assertions:

- `"salary meets floor"` is present in the reasons.
- `"salary below floor"` is NOT present in the reasons.

**Verify**: `uv run --extra dev pytest` → exit 0, "10 passed" (the 9 prior
tests plus the new one).

## Test plan

- New test in `tests/test_engine.py`: a Lever-style job with
  `salary_interval="monthly"`, `salary_max=10000`, scored against
  `salary_floor_usd=100000`, asserting "salary meets floor" is in the reasons
  and "salary below floor" is not. This is the exact regression the plan fixes.
- Model the test structurally on the existing tests in `tests/test_engine.py`
  (same construction of the job/criteria objects and the same way of reading the
  scorer result).
- Verification: `uv run --extra dev pytest` → all pass, "10 passed" (9 existing
  + 1 new).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports "10 passed".
- [ ] `grep -n 'replace("per-"' engine/discovery/ats/lever.py` returns no
      matches (the buggy mapping is gone).
- [ ] `grep -n '"weekly"' engine/scoring/fit.py` returns a match (the
      multiplier table was extended).
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0 (unaffected).
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row for plan 003 updated to DONE.

## STOP conditions

Stop and report back (do not improvise) if:

- The code at `engine/discovery/ats/lever.py:46` is not
  `salary_interval=(sal.get("interval") or "").replace("per-", "") or None`, or
  the annualization line in `engine/scoring/fit.py` is not
  `{"hourly": 2080, "monthly": 12, "yearly": 1}.get(interval, 1)` — the codebase
  has drifted since this plan was written.
- The existing tests in `tests/test_engine.py` do not expose a scorer result
  with an inspectable reasons list in the shape the existing salary/scoring
  tests rely on (you cannot model the new test on them without inventing an API).
- `uv run --extra dev pytest` reports anything other than "9 passed" before your
  changes — the baseline is wrong and the new "10 passed" target is meaningless.
- A step's verification fails twice after a reasonable fix attempt.
- The fix appears to require touching an out-of-scope file (another ATS adapter,
  the job model, or the scorer's floor/weight semantics).

## Maintenance notes

For the human/agent who owns this code after the change lands:

- `_norm_interval` in `engine/discovery/ats/lever.py` is the single source of
  truth for Lever interval normalization. If Lever introduces a new cadence
  (e.g. bi-weekly), add the substring branch here AND a matching multiplier in
  the `fit.py` annualization table — the two must stay in lock-step.
- The annualization multipliers in `engine/scoring/fit.py` (2080 hours/yr, 260
  days/yr, 52 weeks/yr, 12 months/yr) are conventional approximations; if the
  product wants exact business-day or contracted-hours math, that is a separate
  change.
- Reviewer should confirm the new test fails on the pre-fix code (revert either
  source edit and re-run) to prove it actually guards the regression.
- Deferred out of scope: auditing the other ATS adapters to confirm they all
  emit canonical intervals. They are believed correct; a one-time audit is a
  reasonable follow-up but not required for this fix.
