# Plan 002: `atlas discover --only indeed|linkedin` actually fetches those sites

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the change for the record.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- engine/discovery/runner.py tests/test_engine.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: docs/bug
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

The `discover` CLI command advertises `--only ats,jobspy,indeed,linkedin,himalayas,adzuna`
as selectable sources (`engine/cli.py:73`), but the discovery runner only ever
checks `want("jobspy")` to decide whether to run the JobSpy block
(`engine/discovery/runner.py:80`). It never checks `indeed` or `linkedin`. So a
user who runs `atlas discover --only indeed` (or `--only linkedin`) skips the
entire JobSpy block and gets **zero jobs back** with no error — a silent,
confusing dead end for a documented flag. The per-site results are already
stored under the labels `indeed` / `linkedin` (`runner.py:87-88`), so those
labels exist in the output but cannot be *selected* as inputs. This change makes
the documented per-site selection actually work, so the help string at
`cli.py:73` becomes accurate rather than aspirational.

## Current state

Files involved:

- `engine/cli.py` — the typer `discover` command; parses `--only` into a set and
  forwards it to the runner. The help string lists the selectable sources.
- `engine/discovery/runner.py` — the discovery orchestrator; `want(name)` gates
  each source block. The JobSpy block fetches per-site results and stores them
  under per-site labels.
- `tests/test_engine.py` — existing test suite; new test is modeled after the
  tests already here.

### `engine/cli.py:71-91` — discover command + `--only` parsing

```python
@app.command()
def discover(
    only: Optional[str] = typer.Option(None, help="Comma list to limit sources: ats,jobspy,indeed,linkedin,himalayas,adzuna"),
) -> None:
    """Pull jobs from all enabled sources into the database (idempotent)."""
    from engine.discovery.runner import discover as run_discover
    only_set = {s.strip() for s in only.split(",")} if only else None
    with _db() as db:
        summary = run_discover(db, only=only_set)
```

The help string at line 73 lists `indeed,linkedin` as valid `--only` values; the
parsing at line 77 passes them straight through as a set. The CLI is already
correct — the bug is entirely in the runner.

### `engine/discovery/runner.py:28-37` — `discover` signature

```python
def discover(db: DB, *, sources_cfg: Optional[dict] = None,
             companies: Optional[list[CompanyTarget]] = None,
             terms: Optional[list[str]] = None,
             only: Optional[set[str]] = None) -> dict:
    cfg = sources_cfg or load_sources()
    companies = companies if companies is not None else load_companies()
    terms = terms or cfg.get("search_terms", [])
    limits = cfg.get("limits", {})
    cap = int(limits.get("max_jobs_per_run", 400))
    client = make_client(timeout=float(limits.get("per_source_timeout_s", 45)))
```

`only` is an optional set of source names. `cfg["jobspy"]` is the JobSpy config
dict passed to `jobspy_source.fetch`.

### `engine/discovery/runner.py:69` — the `want` gate

```python
    want = lambda name: (only is None) or (name in only)
```

### `engine/discovery/runner.py:79-88` — JobSpy block + per-site store (the bug)

```python
    # 2. JobSpy — Indeed + LinkedIn guest (health-logged per site).
    if want("jobspy") and cfg.get("jobspy", {}).get("enabled", True):
        try:
            per_site = jobspy_source.fetch(cfg["jobspy"], terms)
        except Exception as e:  # noqa: BLE001
            per_site = {}
            db.log_source_health("jobspy", False, 0, str(e)[:300], 0)
            summary["errors"].append(f"jobspy: {e}")
        for site, jobs in per_site.items():
            store(site, lambda jobs=jobs: jobs)
```

The block is gated only on `want("jobspy")` at line 80. When `only={"indeed"}`,
`want("jobspy")` is `False`, so the block never runs. Note line 88 stores each
result under its own `site` label (`indeed`, `linkedin`), which is why those
labels appear in output but are not honored as *inputs*.

### Conventions to match (state and follow these)

- `from __future__ import annotations` at the top of every module (see
  `runner.py:7`).
- typer CLI; pydantic v2 models; `rich.console` for output.
- sqlite3 with **parameterized** queries + WAL; `@dataclass` result objects;
  sha1 16-char natural keys; UPSERT + COALESCE gap-fill (DB layer — not touched
  by this plan, but do not introduce string-interpolated SQL anywhere).
- Tests live in `tests/test_engine.py`. **Model the new test on the existing
  tests in that file** — same import style, fixtures, and monkeypatch idioms.
  Read the existing tests before writing the new one.

## Commands you will need

| Purpose            | Command                                              | Expected on success            |
|--------------------|------------------------------------------------------|--------------------------------|
| Python tests       | `uv run --extra dev pytest`                          | exit 0, "9 passed" (10 after the new test) |
| Run one test       | `uv run --extra dev pytest tests/test_engine.py -k <name>` | exit 0, selected test passes   |
| Frontend typecheck | `npm --prefix dashboard/frontend run typecheck`      | exit 0, no errors              |
| Frontend build     | `npm --prefix dashboard/frontend run build`          | exit 0                         |

Do NOT use bare `pytest` — it resolves to a global interpreter missing `docx`,
`rapidfuzz`, and `reportlab` and will falsely fail 2 tests. Always go through
`uv run --extra dev pytest`. This plan touches only Python; the frontend
commands are listed for completeness and are not expected to change.

## Scope

**In scope** (the only files you should modify):
- `engine/discovery/runner.py`
- `tests/test_engine.py` (add one new test)

**Out of scope** (do NOT touch, even though they look related):
- `engine/cli.py` — the help string at line 73 is now accurate after this fix;
  changing it is unnecessary and would widen the diff.
- `engine/discovery/jobspy_source.py` — its internals (how it reads `cfg["sites"]`
  / fetches) are not changed. This plan only filters the config dict *before*
  calling `fetch`; it relies on the existing behavior of `fetch` honoring the
  `sites` it is given.
- The DB layer, scoring, brain, dashboard — unrelated.

## Git workflow

- Branch: `advisor/002-only-indeed-linkedin` (off the latest `master`).
- Add only the two in-scope files **by name** — never `git add .` / `git add -A`.
- Commit per logical unit; concise imperative message, e.g.
  `discover: honor --only indeed|linkedin by filtering jobspy sites`.
- Do NOT push or open a PR unless the operator explicitly instructs it.

## Steps

### Step 1: Gate the JobSpy block on per-site selection and filter its sites

In `engine/discovery/runner.py`, change the JobSpy block (currently
lines 79-88) so it runs when any of `jobspy`, `indeed`, or `linkedin` is wanted,
and so that when only specific sites are requested it fetches only those sites.

Target shape:

```python
    # 2. JobSpy — Indeed + LinkedIn guest (health-logged per site).
    # `jobspy` selects all configured sites; `indeed`/`linkedin` select that
    # one site. Honor whichever the caller asked for.
    JOBSPY_SITES = ("indeed", "linkedin")
    if want("jobspy") and cfg.get("jobspy", {}).get("enabled", True):
        jobspy_cfg = cfg["jobspy"]
        if only is not None and "jobspy" not in only:
            wanted_sites = [s for s in JOBSPY_SITES if s in only]
            jobspy_cfg = {**jobspy_cfg, "sites": wanted_sites}
        try:
            per_site = jobspy_source.fetch(jobspy_cfg, terms)
        except Exception as e:  # noqa: BLE001
            per_site = {}
            db.log_source_health("jobspy", False, 0, str(e)[:300], 0)
            summary["errors"].append(f"jobspy: {e}")
        for site, jobs in per_site.items():
            store(site, lambda jobs=jobs: jobs)
```

The `if want("jobspy") and ...` condition on the *outer* block must be widened
to also fire for per-site selection. Replace the gate so the block runs when
`want("jobspy") or want("indeed") or want("linkedin")` AND the JobSpy config is
enabled. Concretely:

```python
    if (want("jobspy") or want("indeed") or want("linkedin")) \
            and cfg.get("jobspy", {}).get("enabled", True):
```

Inside the block, build `jobspy_cfg`: when `only` is a set that does **not**
contain `"jobspy"` (i.e. the caller asked for specific sites, not the
all-sites alias), shallow-copy the config and override its `"sites"` key with
only the requested JobSpy sites (`[s for s in ("indeed","linkedin") if s in only]`).
When `only is None` or `only` contains `"jobspy"`, pass the original config
unchanged (backward-compatible: `jobspy` remains an alias selecting all sites).

Do not change the per-site `store(...)` loop — it already labels results by site.

**Verify**: `uv run --extra dev pytest tests/test_engine.py` → exit 0, all
existing tests still pass (no regression from the gate/config change).

### Step 2: Add a unit test pinning the per-site selection behavior

In `tests/test_engine.py`, add one test that:

1. Monkeypatches `engine.discovery.jobspy_source.fetch` with a capturing stub
   that records the `cfg` it was called with and returns an empty per-site dict
   (e.g. `{}` or `{"indeed": []}`), so no network is hit.
2. Calls `discover(db, only={"indeed"})` with a minimal in-memory DB and an
   explicit `sources_cfg` that enables `jobspy` with `sites=["indeed","linkedin"]`
   and disables the other sources (`ats`, `himalayas`, `adzuna`) so only the
   JobSpy path is exercised. Pass `companies=[]` and `terms=[...]` so it does not
   read config files.
3. Asserts the captured `cfg["sites"] == ["indeed"]` — proving the JobSpy block
   ran AND its sites were filtered to the requested site.
4. Asserts that calling `discover(db, only={"ats"})` (with the same stub) does
   **not** invoke the stub — proving the JobSpy block is skipped when neither
   `jobspy` nor `indeed`/`linkedin` is selected. (Use a flag/counter on the stub
   or assert the captured cfg list stays empty.)

Match the import style, fixture/DB-construction idiom, and `monkeypatch` usage
already present in `tests/test_engine.py` — read the file's existing tests first
and mirror them. Use a descriptive test name such as
`test_discover_only_indeed_filters_jobspy_sites`.

**Verify**: `uv run --extra dev pytest tests/test_engine.py -k only_indeed` →
exit 0, the new test passes.

### Step 3: Full suite green

Run the full Python suite to confirm no regression and that the new test is
counted.

**Verify**: `uv run --extra dev pytest` → exit 0, "10 passed" (the prior 9 plus
the 1 new test).

## Test plan

- New test in `tests/test_engine.py`:
  `test_discover_only_indeed_filters_jobspy_sites` covering:
  - **the regression this plan fixes**: `discover(db, only={"indeed"})` runs the
    JobSpy block (it previously did not) with `cfg["sites"] == ["indeed"]`.
  - **the negative case**: `discover(db, only={"ats"})` does NOT call
    `jobspy_source.fetch`.
- Structural pattern: model after the existing tests in `tests/test_engine.py`
  (same fixtures, monkeypatch idiom, in-memory DB construction).
- Network is never hit — `jobspy_source.fetch` is monkeypatched.
- Verification: `uv run --extra dev pytest` → exit 0, "10 passed" including the
  1 new test.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` exits 0 and reports "10 passed".
- [ ] `uv run --extra dev pytest tests/test_engine.py -k only_indeed` passes the
      new test.
- [ ] `grep -n 'want("indeed")' engine/discovery/runner.py` returns a match
      (the gate now checks `indeed`).
- [ ] `grep -n 'want("linkedin")' engine/discovery/runner.py` returns a match.
- [ ] Only `engine/discovery/runner.py` and `tests/test_engine.py` are modified
      (`git status` shows no other changed files).
- [ ] `plans/README.md` status row for plan 002 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The JobSpy block in `engine/discovery/runner.py` no longer matches the
  "Current state" excerpt at lines 79-88 (e.g. the gate already checks `indeed`,
  or `jobspy_source.fetch` is called differently) — the codebase has drifted.
- `jobspy_source.fetch` does **not** read a `"sites"` key from its config dict
  (open `engine/discovery/jobspy_source.py` to confirm the key name before
  relying on it). If the key is named differently (e.g. `"site_name"`), the
  config-filtering override must use that real key — stop and confirm rather
  than guessing.
- The baseline `uv run --extra dev pytest` does NOT report "9 passed" before
  your change (something else is already broken — report it, do not build on it).
- A verification command fails twice after a reasonable fix attempt.
- The fix appears to require editing any file outside the in-scope list.

## Maintenance notes

For the human/agent who owns this code after the change lands:

- If a third JobSpy site is ever added (e.g. `glassdoor`), extend `JOBSPY_SITES`
  in `runner.py` and add it to the `--only` help string in `engine/cli.py:73`
  and to the per-site selection test.
- A reviewer should scrutinize: (1) the `jobspy` alias still selects all sites
  (backward-compat) when `only` is `None` or contains `"jobspy"`; (2) the config
  shallow-copy does not mutate the shared `cfg` dict in place; (3) the `"sites"`
  key name matches what `jobspy_source.fetch` actually consumes.
- The CLI help string at `engine/cli.py:73` was intentionally left unchanged —
  it already lists `indeed,linkedin` and is now accurate. No follow-up needed
  there.
