# Plan 017: Root AGENTS.md + one-command scripts/check.sh

> Status: IMPLEMENTED on 2026-06-13 against c3e2679 — this file documents the
> change for the record. It is written in the imperative as the spec that was
> executed; the "Done criteria" remain the machine-checkable acceptance gate.

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat c3e2679..HEAD -- scripts/ pyproject.toml docs/ARCHITECTURE.md brain/SKILL.md`
> If any in-scope or cited file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/007-reproducible-pytest.md
- **Category**: dx
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

A contributor (human or agent) landing in this repo has no single answer to two
basic questions: "how do I prove the repo is healthy?" and "what must I never
break?". The verify invocation is itself non-obvious — a bare `pytest` resolves
to a global interpreter missing `docx`/`rapidfuzz`/`reportlab` and falsely fails
2 tests, so the canonical command (`uv run --extra dev pytest`, see plan 007) is
unguessable from the file tree. Worse, the load-bearing invariants — the CV
never fabricates, the brain never sends, the engine is deterministic, and the
tool costs $0 with no API key — live only in scattered docstrings. This plan
adds a root `AGENTS.md` (the single source of truth for package managers, verify
commands, conventions, and the hard rules) and `scripts/check.sh` (one command
that runs the full health gate and exits non-zero on any failure). After it
lands, "is the repo healthy?" is `bash scripts/check.sh; echo $?`.

## Current state

Files involved:

- `scripts/run.sh` — the **only** script in the repo today; a dashboard
  launcher, not a health check. No `scripts/check.sh` and no root `AGENTS.md`
  or root `CLAUDE.md` exist (confirmed: `ls AGENTS.md scripts/check.sh` →
  both missing at planned-at commit).
- `pyproject.toml` — Python project metadata; defines the `atlas` entrypoint
  and pytest config.
- `docs/ARCHITECTURE.md` — holds the deterministic-vs-LLM split (the
  determinism + $0/no-API-key invariants).
- `brain/SKILL.md` — holds the "Hard rules" block (send-nothing, drafts-only,
  stay-on-subscription).

Exact code as it exists today (do not paraphrase — match these when writing the
new files):

`scripts/run.sh:1-14` — the sole existing script; note the `npm --prefix
dashboard/frontend` invocations and `uv run` usage that `check.sh` must mirror:

```bash
#!/usr/bin/env bash
# Atlas dashboard launcher. Builds the frontend if needed, then serves the app
# (frontend + API) on http://127.0.0.1:8787. Run with:  ./scripts/run.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${1:-8787}"

if [ ! -f dashboard/frontend/dist/index.html ]; then
  echo "Building dashboard frontend..."
  npm --prefix dashboard/frontend install
  npm --prefix dashboard/frontend run build
fi
```

`pyproject.toml:28-40` — entrypoint and pytest config the AGENTS.md must
reference accurately:

```toml
[project.scripts]
atlas = "engine.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["engine"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

`docs/ARCHITECTURE.md:9-14` — the deterministic-vs-LLM split (HARD RULE #1:
the engine is deterministic and degrades gracefully without the LLM; implies
$0/no-API-key):

```markdown
## Deterministic vs LLM
- **`engine/` (Python, no LLM, idempotent):** discovery, dedupe, DB, fit scoring, JD keyword
  extraction, CV render + parse-check, outreach templating, referral match, follow-up schedule.
- **LLM (inside the Cowork run):** nuanced ranking, truthful CV/message wording, why-fit. The
  engine always produces a working baseline, so the tool degrades gracefully without the LLM.
```

`brain/SKILL.md:39-43` — the Hard rules block (HARD RULE #2: send/submit
nothing, drafts only, stay on subscription — no `claude -p`, Agent SDK, or API
key):

```markdown
## Hard rules
- **Send nothing. Submit nothing. No browser automation.** Drafts only.
- Stay on the user's subscription: do not use `claude -p`, the Agent SDK, or an API key.
- Only act on what the pipeline produced; do not invent jobs, contacts, or numbers.
- If `uv run atlas brain` fails, report the error and stop — do not improvise a workaround.
```

Repo conventions the new docs must state (these live in code; AGENTS.md is the
place to surface them):

- **Python 3.11+** across `engine/`, `brain/`, `dashboard/backend/`; **TS +
  React 19 + Vite** in `dashboard/frontend/`. Package managers: **uv** (Python),
  **npm** (frontend).
- typer CLI; pydantic v2 models; `rich.console` for output; `sqlite3` with
  **parameterized** queries + WAL; `@dataclass` result objects;
  `from __future__ import annotations` at the top of modules; sha1 16-char
  natural keys; UPSERT + COALESCE gap-fill on writes. Existing tests live in
  `tests/test_engine.py` — model any new tests after those.
- Canonical verify commands (from plan 007 and the frontend package): the
  truthful test command is `uv run --extra dev pytest` (→ `9 passed`); a bare
  `pytest`/`rtk pytest` resolves to a global interpreter missing
  `docx`/`rapidfuzz`/`reportlab` and falsely fails 2 tests — never use it.

Exemplar script to match for shell style (`set -euo pipefail`, `cd` to repo
root via `$(dirname "$0")/..`, `npm --prefix dashboard/frontend`, `uv run`):
`scripts/run.sh`.

## Commands you will need

| Purpose             | Command                                          | Expected on success            |
|---------------------|--------------------------------------------------|--------------------------------|
| Python tests        | `uv run --extra dev pytest`                      | `9 passed`                     |
| Frontend typecheck  | `npm --prefix dashboard/frontend run typecheck`  | exit 0, no errors              |
| Frontend build      | `npm --prefix dashboard/frontend run build`      | exit 0, `dist/` produced       |
| Full health gate    | `bash scripts/check.sh`                          | exit 0 on a clean tree         |
| Drift check         | `git diff --stat c3e2679..HEAD -- scripts/ pyproject.toml docs/ARCHITECTURE.md brain/SKILL.md` | (see drift-check note) |

(Exact commands from this repo. Do NOT substitute a bare `pytest` — it lies, per
plan 007.)

## Scope

**In scope** (the only files you should create/modify):
- `AGENTS.md` (new, repo root)
- `scripts/check.sh` (new, executable)

**Out of scope** (do NOT touch, even though they look related):
- Any behavioral code under `engine/`, `brain/`, `dashboard/` — this plan is
  documentation + a wrapper script only; changing source risks the determinism
  and hard-rule invariants and is unrelated to the finding.
- `scripts/run.sh` — leave the launcher as-is; `check.sh` is a separate entry.
- `pyproject.toml`, `docs/ARCHITECTURE.md`, `brain/SKILL.md` — read-only here;
  they are quoted, not edited (pytest/dep wiring is plan 007's job).

## Git workflow

- Branch: `advisor/017-agents-md-and-check-script` (based on the latest `main`).
- Commit the two new files by name only — `git add AGENTS.md scripts/check.sh`.
  Never `git add .` / `git add -A`.
- Message style follows the repo's convention (see `git log`, e.g.
  `dx: ...`): `dx: add root AGENTS.md + one-command scripts/check.sh`.
- Do NOT push or open a PR. The operator merges to `main` explicitly.

## Steps

### Step 1: Write `scripts/check.sh`

Create `scripts/check.sh` mirroring the shell style of `scripts/run.sh`
(`set -euo pipefail`, `cd "$(dirname "$0")/.."`). It must run, in order, and
exit non-zero on the first failure (achieved by `set -e`):

1. Install Python deps including the test group. Use the dependency wiring that
   plan 007 establishes — `uv sync` (which, after 007, installs the PEP 735
   `dev` group by default). If plan 007 has NOT yet landed on this branch, the
   equivalent is `uv sync --extra dev`. The script should not assume; have it
   run `uv sync --extra dev` so it is correct under both the pre- and post-007
   layouts.
2. Run the canonical Python tests: `uv run --extra dev pytest`.
3. Install frontend deps deterministically: `npm --prefix dashboard/frontend ci`
   (falls back to `npm --prefix dashboard/frontend install` if no lockfile is
   present — but the repo has one, so prefer `ci`).
4. Typecheck the frontend: `npm --prefix dashboard/frontend run typecheck`.

Echo a clear banner before each phase so a human reading CI logs can see which
phase failed. Target shape:

```bash
#!/usr/bin/env bash
# Atlas health gate. Runs the full verify suite (Python deps + tests, frontend
# deps + typecheck) and exits non-zero on the first failure. Run:  bash scripts/check.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Python deps (uv sync --extra dev)"
uv sync --extra dev

echo "==> Python tests (uv run --extra dev pytest)"
uv run --extra dev pytest

echo "==> Frontend deps (npm ci)"
npm --prefix dashboard/frontend ci

echo "==> Frontend typecheck"
npm --prefix dashboard/frontend run typecheck

echo ""
echo "OK — repo healthy."
```

Make it executable: `chmod +x scripts/check.sh`.

**Verify**: `bash scripts/check.sh; echo "exit=$?"` → ends with the Python suite
reporting `9 passed`, the frontend typecheck clean, the line `OK — repo
healthy.`, and `exit=0`.

### Step 2: Write the root `AGENTS.md`

Create `AGENTS.md` at the repo root. It is the single onboarding doc; keep it
tight. It must contain these sections, with content drawn verbatim from
"Current state" (do not invent commands or rules):

- **Stack & package managers**: Python 3.11+ (`engine/`, `brain/`,
  `dashboard/backend/`) with **uv**; TS + React 19 + Vite (`dashboard/frontend/`)
  with **npm**.
- **Verify (the one command)**: `bash scripts/check.sh`. Spell out the two
  underlying commands and their expected output: `uv run --extra dev pytest`
  (→ `9 passed`) and `npm --prefix dashboard/frontend ci && npm --prefix
  dashboard/frontend run typecheck`. Add the warning that a bare `pytest` /
  `rtk pytest` hits a global interpreter missing `docx`/`rapidfuzz`/`reportlab`
  and falsely fails 2 tests — always go through `uv run`.
- **Conventions**: typer CLI; pydantic v2; `rich.console`; `sqlite3`
  parameterized queries + WAL; `@dataclass` results; `from __future__ import
  annotations`; sha1 16-char natural keys; UPSERT + COALESCE gap-fill. New tests
  go in `tests/` and are modeled after `tests/test_engine.py`.
- **HARD RULES** (quote both, attributing source):
  - From `docs/ARCHITECTURE.md`: the `engine/` is deterministic / idempotent /
    no-LLM and always produces a working baseline; the tool runs at **$0 with
    no API key** (the LLM work happens inside the Cowork run on the user's
    subscription).
  - From `brain/SKILL.md`: **Send nothing. Submit nothing. No browser
    automation. Drafts only.** Stay on the user's subscription — no `claude -p`,
    Agent SDK, or API key. Only act on what the pipeline produced; never invent
    jobs, contacts, or numbers.
- **Entrypoint**: the CLI is `atlas` → `engine.cli:app` (per
  `pyproject.toml:28-29`); run via `uv run atlas …`.

**Verify**:
`test -f AGENTS.md && grep -q "uv run --extra dev pytest" AGENTS.md && grep -q "Send nothing" AGENTS.md && grep -q "scripts/check.sh" AGENTS.md && echo OK`
→ prints `OK`.

### Step 3: Update the plans index

Set this plan's row in `plans/README.md` to `DONE`.

**Verify**: `grep -n "^| 017" plans/README.md` → row shows `DONE`.

## Test plan

This plan adds no Python/TS source, so it introduces no new unit tests — the
existing suite is the regression net. The new `scripts/check.sh` is itself
exercised as the acceptance test.

- No new files under `tests/`.
- Existing structural pattern for reference only (not modified):
  `tests/test_engine.py`.
- Verification: `bash scripts/check.sh` runs the existing `uv run --extra dev
  pytest` suite (→ `9 passed`) plus the frontend typecheck, and exits 0.

## Done criteria

Machine-checkable. ALL must hold on a clean tree:

- [ ] `test -x scripts/check.sh` → exit 0 (file exists and is executable)
- [ ] `test -f AGENTS.md` → exit 0
- [ ] `bash scripts/check.sh; echo $?` → final line of the run is `OK — repo healthy.` and `$?` is `0`
- [ ] `uv run --extra dev pytest` → `9 passed`
- [ ] `npm --prefix dashboard/frontend run typecheck` → exit 0
- [ ] `grep -q "uv run --extra dev pytest" AGENTS.md && grep -q "Send nothing" AGENTS.md && grep -q "scripts/check.sh" AGENTS.md` → exit 0
- [ ] `git status --porcelain` lists ONLY `AGENTS.md` and `scripts/check.sh` (plus `plans/README.md`); no source files modified
- [ ] `plans/README.md` row 017 shows `DONE`

## STOP conditions

Stop and report back (do not improvise) if:

- The drift check shows `scripts/run.sh`, `pyproject.toml`,
  `docs/ARCHITECTURE.md`, or `brain/SKILL.md` changed since `c3e2679` and the
  quoted excerpts in "Current state" no longer match the live files — the rules
  or commands you are about to enshrine may be stale.
- `uv run --extra dev pytest` does NOT report exactly `9 passed` (e.g. reports
  `7 passed, 2 failed`, which means you ran a bare/global `pytest`, or plan 007
  has regressed the dependency wiring). Do not "fix" tests to make `check.sh`
  green.
- `uv sync --extra dev` errors because the `dev` extra/group does not exist
  under the current `pyproject.toml` layout — confirm whether plan 007 has
  landed and adjust the install line accordingly, then report.
- The frontend typecheck fails on `main` independent of this change (pre-existing
  TS errors) — `check.sh` should surface that, but do not edit frontend source
  to silence it.
- Writing `AGENTS.md` would require restating a rule you cannot find verbatim in
  `docs/ARCHITECTURE.md:9-14` or `brain/SKILL.md:39-43` — do not paraphrase or
  invent invariants.
- The fix appears to require touching any out-of-scope file.

## Maintenance notes

For the human/agent who owns this after the change lands:

- `scripts/check.sh` and `AGENTS.md` both hard-code the verify commands. If the
  Python dependency wiring changes (plan 007 / 008) or the frontend scripts in
  `dashboard/frontend/package.json` are renamed, both files must be updated in
  lockstep — they are the canonical statement of "how to verify".
- The expected `9 passed` count is asserted in the Done criteria; when tests are
  added, bump that number here and in any CI that greps for it.
- A reviewer should scrutinize that `check.sh` uses `uv run --extra dev pytest`
  (not a bare `pytest`) and that the HARD RULES in `AGENTS.md` match the source
  docstrings word-for-word — drift between AGENTS.md and the source rules is the
  main long-term risk.
- Deferred out of this plan: wiring `scripts/check.sh` into CI (a GitHub Actions
  workflow). This plan only provides the local one-command gate; CI adoption is
  a separate follow-up.
