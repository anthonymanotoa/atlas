# Plan 007: Make `uv run pytest` reproducibly green

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the
> change for the record.

> **Executor instructions**: This plan was already executed. It is written as
> the spec that was carried out, in the imperative. If you are re-running it
> (e.g. on a fresh checkout that drifted), follow it step by step, run every
> verification command, and confirm the expected result before moving on. If
> anything in the "STOP conditions" section occurs, stop and report — do not
> improvise. When done, update the status row for this plan in
> `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat c3e2679..HEAD -- pyproject.toml README.md`
> If either in-scope file changed since this plan was written, compare the
> "Current state" excerpts below against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `c3e2679`, 2026-06-13
- **Issue**: (none)

## Why this matters

Finding **DX-01 (HIGH)**: the test suite is green, but the *canonical* command to
run it is ambiguous, and the two obvious guesses both lie. `pytest` and
`pytest-asyncio` live in `[project.optional-dependencies].dev`, which a plain
`uv sync` does **not** install. Worse, a bare `pytest` / `rtk pytest` resolves to
a global interpreter (miniconda) that is missing `docx`, `rapidfuzz`, and
`reportlab`, so it falsely reports "7 passed, 2 failed" — two failures that are
purely an environment artifact, not a real regression. The only command that
tells the truth is `uv run --extra dev pytest` (→ 9 passed).

Every other plan in this batch ends with a verification gate that runs the tests.
If "run the tests" is a coin-flip between three commands with three different
answers, those gates are worthless and an executor may chase a phantom failure.
This plan makes the canonical `uv run pytest` install its own test deps and pass
out of the box, and documents the one true command, so every downstream
verification is unambiguous.

## Current state

Files involved:

- `pyproject.toml` — project + dependency metadata; the dev test deps live in an
  *optional* group that `uv sync` skips (lines 25–26), and the pytest config
  block is at lines 38–40.
- `README.md` — Quick start lists `uv sync` and `uv run atlas …` (lines 56–68)
  but has **no** "run the tests" command anywhere.
- `tests/test_engine.py` — the existing (and only) test module; new tests are
  modeled after it. Its docstring states what the 9 tests lock down.

Exact code as it exists today.

`pyproject.toml:7-23` — runtime deps (note `python-docx`, `rapidfuzz`,
`reportlab` are here; the global interpreter lacks them, which is why a bare
`pytest` falsely fails):

```toml
dependencies = [
    "python-jobspy>=1.1.82",
    "httpx>=0.27",
    "typer>=0.12",
    "rich>=13.7",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "pyyaml>=6.0",
    "python-docx>=1.1",
    "docxtpl>=0.18",
    "jinja2>=3.1",
    "rapidfuzz>=3.9",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.30",
    "python-dateutil>=2.9",
    "reportlab>=4.2",
]
```

`pyproject.toml:25-26` — the problem: test deps are *optional*, so `uv sync`
does not install them:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]
```

`pyproject.toml:38-40` — pytest config (correct; do not change):

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`tests/test_engine.py:1-5` — the suite's docstring (defines what the 9 tests
cover; new tests, if any, match this module's style):

```python
"""Unit tests locking the engine's load-bearing guarantees.

These are network-free: dedupe/idempotency, scoring rules, no-fabrication tailoring,
parse-safety, reply-aware follow-ups, and referral matching.
"""
```

Repo conventions that apply here:

- Package manager is **uv** (confirmed `uv 0.11.21`); Python `>=3.11`.
- Tests live in `tests/`, configured via `[tool.pytest.ini_options]` with
  `pythonpath = ["."]` so `engine` / `brain` import without an install step.
- Test style to match (if you ever add tests): `tests/test_engine.py` —
  network-free unit tests, one guarantee per test.
- This repo does not push or open PRs from advisor work (see Git workflow).

Design constraint honored by the chosen approach: **`uv run pytest` must work
with no extra flags after a fresh `uv sync`.** PEP 735 `[dependency-groups]` with
a group named `dev` is installed by `uv sync` by default and auto-activated by
`uv run`, which is exactly that contract. `[project.optional-dependencies]` is
**not** synced by default — hence the move.

## Commands you will need

| Purpose                 | Command                                             | Expected on success            |
|-------------------------|-----------------------------------------------------|--------------------------------|
| Install (incl. dev)     | `uv sync`                                            | exit 0; dev group installed    |
| Tests (canonical)       | `uv run pytest`                                      | `9 passed`                     |
| Tests (explicit, fallback) | `uv run --extra dev pytest`                      | `9 passed`                     |
| Frontend typecheck      | `npm --prefix dashboard/frontend run typecheck`     | exit 0, no errors              |
| Frontend build          | `npm --prefix dashboard/frontend run build`         | exit 0                         |
| uv version check        | `uv --version`                                      | `uv 0.4.27` or newer           |

Notes for the executor:
- **Never** run a bare `pytest` or `rtk pytest` here. It resolves to a global
  miniconda interpreter missing `docx`/`rapidfuzz`/`reportlab` and falsely
  reports "7 passed, 2 failed". Always go through `uv run`.
- The frontend commands are listed only so a reviewer can confirm this plan
  touched nothing on the frontend; this plan changes no TS/React code.

## Scope

**In scope** (the only files modified):
- `pyproject.toml`
- `README.md` (add the canonical test command to Quick start)

**Out of scope** (do NOT touch):
- `tests/test_engine.py` and anything under `tests/` — the tests already pass;
  this plan changes *how they are invoked/installed*, not the tests themselves.
- Any `engine/`, `brain/`, `dashboard/` source — no behavior change.
- The `[tool.pytest.ini_options]` block — it is already correct.
- `uv.lock` beyond what `uv sync` regenerates automatically.

## Git workflow

- Branch: `advisor/007-reproducible-pytest`.
- Commit the two in-scope files only, by name — never `git add .` / `git add -A`:
  `git add pyproject.toml README.md` (and `uv.lock` if `uv sync` regenerated it).
- Commit message style matches the repo log (short imperative subject), e.g.
  `dx: make uv run pytest install its own deps (PEP 735 dev group)`.
- Do NOT push or open a PR. The operator merges to `master` explicitly.

## Steps

### Step 1: Confirm uv supports PEP 735 `[dependency-groups]`

Run `uv --version`. PEP 735 dependency groups are supported from **uv 0.4.27**.
The development environment confirmed `uv 0.11.21`, which is well past that.

If the installed uv is older than 0.4.27, do **not** proceed with Step 2 — go to
the STOP conditions (fallback path).

**Verify**: `uv --version` → prints `uv 0.4.27` or newer.

### Step 2: Move test deps into a uv default-synced `[dependency-groups] dev`

In `pyproject.toml`, replace the optional-dependencies dev group (lines 25–26):

```toml
[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]
```

with a PEP 735 dependency group of the same name and contents:

```toml
[dependency-groups]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]
```

Rationale captured for the reviewer: a group named `dev` under
`[dependency-groups]` is part of uv's **default groups**, so `uv sync` installs
it without `--extra dev`, and `uv run` activates it automatically — making
`uv run pytest` work with no flags. Keep the same package pins; do not add or
remove packages. Leave the `[project] dependencies`, `[project.scripts]`,
`[build-system]`, `[tool.hatch.*]`, and `[tool.pytest.ini_options]` blocks
exactly as they are.

**Verify**:
- `uv sync` → exit 0 (regenerates `uv.lock`/venv with the dev group).
- `uv run pytest` → `9 passed`.

### Step 3: Document the one true test command in the README

`README.md` Quick start (lines 56–68) lists `uv sync` and the `atlas` commands
but no way to run the tests. Add a single explicit line so no one guesses. Append
to the Quick start fenced block (after the dashboard lines), or add a short
"Tests" note immediately below it:

```bash
uv run pytest                             # run the test suite (9 passing)
```

Do not introduce a bare `pytest` example anywhere. If you mention the fallback,
write it as `uv run --extra dev pytest` and note it is only needed on older uv.

**Verify**: `grep -n "uv run pytest" README.md` → at least one match;
`grep -nE "(^|[^-])\bpytest" README.md | grep -v "uv run"` → no bare-`pytest`
invocation lines.

## Test plan

No new tests are written — this is a packaging/DX change, and the in-scope rule
forbids touching `tests/`. The "test" is that the canonical command installs its
deps and passes:

- Existing suite: `tests/test_engine.py` (9 tests, modeled style for any future
  additions).
- Verification: `uv run pytest` → `9 passed` (and `uv run --extra dev pytest`
  → `9 passed` as the explicit fallback, confirming both invocations agree).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv --version` is `0.4.27` or newer.
- [ ] `pyproject.toml` contains a `[dependency-groups]` table with
      `dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]`:
      `grep -n "^\[dependency-groups\]" pyproject.toml` returns a match.
- [ ] The old `[project.optional-dependencies]` dev table is gone:
      `grep -n "^\[project.optional-dependencies\]" pyproject.toml` returns no match.
- [ ] `uv sync` exits 0.
- [ ] `uv run pytest` exits 0 and prints `9 passed`.
- [ ] `uv run --extra dev pytest` also exits 0 and prints `9 passed` (both
      invocations agree).
- [ ] `grep -n "uv run pytest" README.md` returns at least one match.
- [ ] No files outside the in-scope list are modified:
      `git status --porcelain` shows only `pyproject.toml`, `README.md`, and
      possibly `uv.lock`.
- [ ] `plans/README.md` status row for plan 007 updated.

## STOP conditions

Stop and report back (do not improvise) if:

- **The installed uv version does not support `[dependency-groups]`** (older than
  0.4.27, per Step 1). Fallback (do NOT guess): keep
  `[project.optional-dependencies].dev` as-is, document
  `uv run --extra dev pytest` everywhere instead of a bare `uv run pytest`, and
  add a `scripts/check.sh` whose body is `uv run --extra dev pytest "$@"` so
  there is still a single canonical entry point. Report this choice.
- The code in `pyproject.toml` does not match the "Current state" excerpts at
  lines 25–26 (drift since c3e2679) — re-verify before changing anything.
- After Step 2, `uv run pytest` reports anything other than `9 passed` — e.g.
  "7 passed, 2 failed" means the run hit the global miniconda interpreter, not
  the uv venv; do not "fix" the tests. Confirm you are invoking via `uv run`,
  then report.
- `uv sync` fails to resolve or fails to create the venv.
- Applying the fix appears to require touching any file outside the in-scope
  list (especially anything under `tests/` or `engine/`).

## Maintenance notes

For whoever owns this next:

- **Adding more dev tooling** (linters, type checkers, more pytest plugins): add
  them to `[dependency-groups].dev` in `pyproject.toml`, not to
  `[project.optional-dependencies]`, so `uv sync` keeps installing them by
  default and `uv run` keeps picking them up flag-free.
- **The "bare pytest lies" trap is environmental, not in this repo.** It comes
  from a global miniconda interpreter on the dev machine that lacks
  `docx`/`rapidfuzz`/`reportlab`. The fix here removes the ambiguity by making
  `uv run pytest` self-installing; if a contributor reports "2 failing tests,"
  the first question is always "did you run it through `uv run`?"
- **Reviewer focus for the PR**: confirm the dev pins are unchanged across the
  move, that `[tool.pytest.ini_options]` is untouched, and that the README no
  longer offers any bare-`pytest` example that could re-introduce the trap.
- **Related work**: plan 017 (docs) covers stamping the one-true command into
  `AGENTS.md` and any other contributor docs; this plan only owns `README.md`.
