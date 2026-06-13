# Plan 015: Add ruff + eslint/prettier + .editorconfig + pre-commit

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat c3e2679..HEAD -- pyproject.toml dashboard/frontend/package.json .gitignore engine/discovery/runner.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition. This plan is a **design spike + a
> mechanical-only reformat** — read the whole file before touching anything.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/007-*.md
- **Category**: dx
- **Planned at**: commit `c3e2679`, 2026-06-13

## Why this matters

The repo has **no Python linter/formatter/type-checker and no frontend
linter/formatter**. The intent to use ruff is already visible in two places:
`.gitignore` lists `.ruff_cache/` and `.mypy_cache/` (lines 30–31), and source
code carries ruff-specific suppressions like `# noqa: BLE001`
(`engine/discovery/runner.py:49`) — a noqa code that only ruff/flake8 enforce.
Without a configured linter those suppressions are dead weight and style drifts
freely across the Python (`engine/`, `brain/`, `dashboard/backend/`) and the
React/TS frontend (`dashboard/frontend/`). Adding ruff + eslint/prettier +
`.editorconfig` + a pre-commit hook gives every contributor (and every Claude
session) one enforceable style and catches a class of bugs (unused imports,
bare excepts, undefined names) before commit.

**Why this is deferred from the bug/feature plans**: turning on `ruff format`
reformats roughly 3k lines on first run. If that reformat rides along with a
behavioral change it muddies the diff and makes review impossible. So this plan
lands as a **single mechanical-only commit** (formatter + safe autofix, zero
behavioral change), reviewed on its own.

## Current state

Files in scope and their current relevant content:

- `pyproject.toml` — project + dev deps + pytest config. **No `[tool.ruff]`,
  no `[tool.mypy]`** (verified: `grep -nE '\[tool\.(ruff|mypy)' pyproject.toml`
  returns nothing). Dev deps today, `pyproject.toml:25-26`:
  ```toml
  [project.optional-dependencies]
  dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]
  ```
  Python floor, `pyproject.toml:6`:
  ```toml
  requires-python = ">=3.11"
  ```
  Pytest config, `pyproject.toml:38-40`:
  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["."]
  testpaths = ["tests"]
  ```

- `dashboard/frontend/package.json` — Vite + React 19 + TS 5.6 project.
  **No eslint, no prettier** in `devDependencies`. Scripts today,
  `package.json:6-12`:
  ```json
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "audit:prod": "npm audit --omit=dev"
  },
  ```
  Existing devDependencies (`package.json:25-33`) include `typescript: ^5.6.3`,
  `@types/react: ^19.0.0`, `@vitejs/plugin-react: ^4.3.4`, `vite: ^6.0.3` —
  no linting/formatting tooling.

- `.gitignore` — already ignores the linter caches (intent signal),
  `.gitignore:29-31`:
  ```
  .pytest_cache/
  .mypy_cache/
  .ruff_cache/
  ```
  **No `.editorconfig` and no `.pre-commit-config.yaml` exist** at repo root
  (verified: `ls -a | grep -iE 'editorconfig|pre-commit'` returns nothing).

- `engine/discovery/runner.py` — has a ruff-style suppression with no linter
  to honor it, `engine/discovery/runner.py:49`:
  ```python
          except Exception as e:  # noqa: BLE001
              ok, err = False, f"{type(e).__name__}: {e}"[:300]
  ```

Repo conventions the config MUST preserve (do not let any tool rewrite these):

- **`from __future__ import annotations`** at module top — keep it; do not let
  an "unused import" rule strip it. ruff's `F` rules already special-case it,
  but if you add an `I` (isort) rule it must not reorder it below other imports.
- typer CLI (`engine/cli:app`, see `pyproject.toml:28-29`), pydantic v2 models,
  `rich.console`, sqlite3 parameterized queries + WAL, `@dataclass` results,
  sha1 16-char natural keys, UPSERT + COALESCE gap-fill. None of these are
  style choices a formatter touches, but the linter ruleset must not flag them
  (e.g. do not enable rules that ban `@dataclass` or rewrite f-strings used in
  the error truncation at `runner.py:49-50`).
- Existing `# noqa: BLE001` suppressions (e.g. `runner.py:49`) must keep
  working — i.e. ruff must be the configured linter and `BLE` must be in (or
  selectable under) its rule set so the noqa is meaningful rather than an
  "unused noqa" warning.
- Package managers: **uv** for Python, **npm** for frontend.

## Commands you will need

| Purpose                 | Command                                          | Expected on success            |
|-------------------------|--------------------------------------------------|--------------------------------|
| Sync dev deps           | `uv sync --extra dev`                            | exit 0                         |
| Python tests            | `uv run --extra dev pytest`                      | `9 passed`                     |
| ruff lint (check only)  | `uv run --extra dev ruff check .`                | exit 0 (after fixes)           |
| ruff format (check)     | `uv run --extra dev ruff format --check .`       | exit 0 (after format)          |
| ruff format (apply)     | `uv run --extra dev ruff format .`               | reports files reformatted      |
| ruff autofix (safe)     | `uv run --extra dev ruff check --fix .`          | reports fixes applied          |
| Frontend install        | `npm --prefix dashboard/frontend install`        | exit 0                         |
| Frontend typecheck      | `npm --prefix dashboard/frontend run typecheck`  | exit 0, no errors              |
| Frontend build          | `npm --prefix dashboard/frontend run build`      | exit 0, build succeeds         |
| Frontend lint           | `npm --prefix dashboard/frontend run lint`       | exit 0 (after fixes)           |
| Frontend format (check) | `npm --prefix dashboard/frontend run format:check` | exit 0 (after format)        |

Do **NOT** use bare `pytest` — the global interpreter is missing `docx`,
`rapidfuzz`, and `reportlab` and will falsely fail 2 tests. Always
`uv run --extra dev pytest`, which must report `9 passed`.

## Suggested executor toolkit

- ruff docs for rule codes: <https://docs.astral.sh/ruff/rules/> — confirm
  `BLE001` is under the `BLE` (flake8-blind-except) group before relying on the
  existing noqa.
- typescript-eslint flat-config docs: <https://typescript-eslint.io/getting-started/>
  — this repo uses ESLint flat config (`eslint.config.js`), not legacy
  `.eslintrc`.
- pre-commit docs: <https://pre-commit.com/> — for the `ruff-pre-commit` hook.

## Scope

**In scope** (the only files you should create/modify):

- `pyproject.toml` — add ruff to dev deps + a minimal `[tool.ruff]` block.
- `dashboard/frontend/package.json` — add eslint/prettier devDeps + `lint`,
  `lint:fix`, `format`, `format:check` scripts.
- `dashboard/frontend/eslint.config.js` (create) — flat config, TS + React.
- `dashboard/frontend/.prettierrc.json` (create) — prettier config.
- `dashboard/frontend/.prettierignore` (create) — exclude `dist/`, build output.
- `.editorconfig` (create) — repo-root editor defaults.
- `.pre-commit-config.yaml` (create) — ruff + ruff-format + frontend typecheck.
- `uv.lock` and `dashboard/frontend/package-lock.json` — regenerated by the
  install/sync commands (commit them).
- **The resulting mechanical reformat** of `engine/`, `brain/`,
  `dashboard/backend/` (ruff) and `dashboard/frontend/src/` (prettier). This is
  expected to be large (~3k lines) and must be **purely mechanical**.

**Out of scope** (do NOT touch, even though they look related):

- **Any behavioral change.** This is a formatting/lint-config commit only. If a
  lint rule wants you to change logic (not just whitespace/imports), **disable
  that rule** rather than rewrite the code — defer real refactors to their own
  plan.
- **mypy / type-checking config.** Despite `.mypy_cache/` in `.gitignore`, do
  NOT add `[tool.mypy]` or a mypy hook here. Type-checking is a separate effort
  with its own noise budget. Leave it for a future plan.
- **Removing existing `# noqa` comments** (e.g. `runner.py:49`). Keep them; the
  ruleset must make them valid, not delete them.
- **`engine/cli.py` behavior, pydantic models, sqlite schema, query strings.**
  Formatting only.
- Vite config (`vite.config.ts`) and tailwind setup — do not reconfigure the
  build.

## Git workflow

- Branch: `advisor/015-linting-and-formatting` (off latest `master`).
- Commit in this order so each commit is reviewable:
  1. `chore(dx): add ruff, eslint/prettier, editorconfig, pre-commit configs`
     — config files + dep/lockfile changes only, **no reformatted source**.
  2. `style: apply ruff format + ruff --fix (mechanical, no behavior change)`
     — the Python reformat only.
  3. `style: apply prettier (mechanical, no behavior change)` — the frontend
     reformat only.
  Splitting config from reformat lets a reviewer diff the config in isolation
  and skim the reformat as "all whitespace/imports".
- Stage files **by name** (`git add <file>`), never `git add .` / `-A`.
- Do NOT push or open a PR unless the operator instructs it.

## Steps

### Step 1: Add ruff config and dev dependency (no reformat yet)

Edit `pyproject.toml`. Add `ruff` to the dev extra and a minimal `[tool.ruff]`
block aligned to the existing style. Target shape:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23", "ruff>=0.6"]
```

Add (e.g. after the `[tool.pytest.ini_options]` block):

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
extend-exclude = ["dashboard/frontend"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "BLE", "C4", "SIM"]
ignore = ["E501"]  # line length handled by formatter, not lint errors

[tool.ruff.format]
quote-style = "double"
```

Rationale baked in: `BLE` keeps `# noqa: BLE001` at `runner.py:49` meaningful;
`I` enables import sorting but ruff keeps `from __future__ import annotations`
first; `line-length = 100` is a deliberate choice — verify it does not explode
diffs (see Step 2). Do **not** run any formatter in this step.

**Verify**: `uv sync --extra dev` → exit 0; then
`uv run --extra dev ruff check . --statistics` → runs and prints a violation
summary (a non-zero count is fine here; you fix in Step 2).

### Step 2: Apply ruff format + safe autofix (mechanical Python reformat)

Run, in order:

```
uv run --extra dev ruff format .
uv run --extra dev ruff check --fix .
```

Use **only the default safe fixers** — do NOT pass `--unsafe-fixes`. After the
run, inspect the diff and confirm it is whitespace, quote normalization, and
import reordering only. Any hunk that changes control flow, a literal value, an
identifier, or removes a line of logic is a STOP condition (see below) — revert
that hunk and add the offending rule to `ignore` in `[tool.ruff.lint]`.

**Verify**:
- `uv run --extra dev ruff format --check .` → exit 0 (nothing left to format).
- `uv run --extra dev ruff check .` → exit 0 (no remaining violations; if a
  legitimate one survives, suppress with a targeted `# noqa: <CODE>` or add to
  `ignore`, do not rewrite logic).
- `uv run --extra dev pytest` → `9 passed`. **Tests passing is the proof the
  reformat was behavior-preserving.**
- `git grep -n "noqa: BLE001" engine/discovery/runner.py` → still present (the
  suppression survived and is not flagged as unused).

### Step 3: Add `.editorconfig` at repo root

Create `/.editorconfig`:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space

[*.py]
indent_size = 4

[*.{ts,tsx,js,jsx,json,css}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

**Verify**: `test -f .editorconfig && echo OK` → `OK`. (Editorconfig has no CLI
gate in this repo; the file existing with `root = true` is the criterion.)

### Step 4: Add eslint + prettier to the frontend

Edit `dashboard/frontend/package.json`: add devDeps and scripts.

Add devDependencies (resolve exact versions via `npm install` in the next
verify; floors shown):

```json
"eslint": "^9.0.0",
"@eslint/js": "^9.0.0",
"typescript-eslint": "^8.0.0",
"eslint-plugin-react-hooks": "^5.0.0",
"eslint-plugin-react-refresh": "^0.4.0",
"prettier": "^3.0.0"
```

Add scripts (alongside the existing `typecheck`, do not remove existing ones):

```json
"lint": "eslint . --max-warnings 0",
"lint:fix": "eslint . --fix",
"format": "prettier --write \"src/**/*.{ts,tsx,css,json}\"",
"format:check": "prettier --check \"src/**/*.{ts,tsx,css,json}\""
```

Create `dashboard/frontend/eslint.config.js` (flat config, React 19 + TS):

```js
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
);
```

Create `dashboard/frontend/.prettierrc.json`:

```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all",
  "printWidth": 100
}
```

Create `dashboard/frontend/.prettierignore`:

```
dist
node_modules
```

**Verify**: `npm --prefix dashboard/frontend install` → exit 0 (writes
`package-lock.json`); then
`npm --prefix dashboard/frontend run lint` → runs (non-zero violation count is
fine here; fixed in Step 5).

### Step 5: Apply prettier + eslint autofix (mechanical frontend reformat)

Run:

```
npm --prefix dashboard/frontend run format
npm --prefix dashboard/frontend run lint:fix
```

Inspect the diff — whitespace/quote/semicolon changes only. Any eslint autofix
that alters logic is a STOP condition; instead set that rule to `"off"` or
`"warn"` in `eslint.config.js`.

**Verify**:
- `npm --prefix dashboard/frontend run format:check` → exit 0.
- `npm --prefix dashboard/frontend run lint` → exit 0.
- `npm --prefix dashboard/frontend run typecheck` → exit 0, no errors.
- `npm --prefix dashboard/frontend run build` → exit 0, build succeeds. (Proof
  the reformat did not break the bundle.)

### Step 6: Wire a lightweight pre-commit hook

Create `/.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: frontend-typecheck
        name: frontend typecheck (tsc --noEmit)
        entry: npm --prefix dashboard/frontend run typecheck
        language: system
        pass_filenames: false
        files: ^dashboard/frontend/.*\.(ts|tsx)$
```

Keep it lightweight: ruff (lint+format) for Python, `tsc --noEmit` for the
frontend. Do NOT add mypy or the full eslint run to pre-commit (eslint stays a
manual/CI script to keep commits fast).

**Verify**: `uv run --extra dev pre-commit run --all-files` (install pre-commit
into the dev env first if absent: it is not a hard dep — running the hook tools
directly per Steps 2 and 5 already gates the code; this step proves the config
parses). Expected: ruff and ruff-format hooks pass (exit 0) since Step 2
already formatted everything. If `pre-commit` is unavailable in the env, the
fallback gate is: `test -f .pre-commit-config.yaml && echo OK` → `OK` plus the
ruff/format checks from Step 2 passing.

## Test plan

This plan writes **no new application tests** — it is config + mechanical
reformat. The existing suite is the regression gate: the reformat must not
change any test outcome.

- Run `uv run --extra dev pytest` before Step 2 and after Step 2/5 — both must
  report `9 passed`. A change in pass count means the "mechanical" reformat
  altered behavior → STOP.
- Existing tests live in `tests/test_engine.py`; do not add or modify them.
- Frontend has no test runner configured — `typecheck` + `build` succeeding are
  the frontend regression gates.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run --extra dev pytest` → `9 passed`
- [ ] `uv run --extra dev ruff check .` exits 0
- [ ] `uv run --extra dev ruff format --check .` exits 0
- [ ] `npm --prefix dashboard/frontend run lint` exits 0
- [ ] `npm --prefix dashboard/frontend run format:check` exits 0
- [ ] `npm --prefix dashboard/frontend run typecheck` exits 0
- [ ] `npm --prefix dashboard/frontend run build` exits 0
- [ ] `grep -nE '\[tool\.ruff\]' pyproject.toml` returns a match
- [ ] `grep -nE '\[tool\.mypy\]' pyproject.toml` returns **no** match (mypy out of scope)
- [ ] `test -f .editorconfig && test -f .pre-commit-config.yaml && test -f dashboard/frontend/eslint.config.js && test -f dashboard/frontend/.prettierrc.json && echo OK` → `OK`
- [ ] `git grep -n "noqa: BLE001" engine/discovery/runner.py` still returns the line
- [ ] No files outside the in-scope list are modified (`git status` shows only in-scope paths + lockfiles + reformatted source under `engine/`, `brain/`, `dashboard/backend/`, `dashboard/frontend/src/`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts —
  e.g. `pyproject.toml:25-26` already has a `[tool.ruff]` block, or
  `runner.py:49` no longer carries `# noqa: BLE001` (the codebase drifted since
  this plan was written; the drift check at the top will catch this).
- After `ruff check --fix` or `eslint --fix`, the diff contains **any non-mechanical
  hunk** — a changed control-flow construct, a changed literal/value, a renamed
  identifier, or removed logic. Do not commit it. Revert that hunk, suppress the
  rule, and report which rule caused it.
- `uv run --extra dev pytest` reports anything other than `9 passed` after the
  reformat (the reformat changed behavior).
- `npm --prefix dashboard/frontend run build` fails after the prettier/eslint
  pass.
- ruff or eslint flags `# noqa: BLE001` (or any existing suppression) as an
  "unused noqa" — the ruleset is misconfigured; fix the `select` list, do not
  delete the suppression.
- A lint rule appears to require touching an out-of-scope file (pydantic models,
  sqlite query strings, `engine/cli.py` logic) to satisfy it — disable the rule
  instead and report it.
- The first-run reformat is dramatically larger or smaller than the ~3k-line
  estimate in a way that suggests a config mistake (e.g. `extend-exclude` not
  honored and it reformatted `node_modules` or generated output).

## Maintenance notes

For whoever owns DX after this lands:

- **Reviewer focus**: review the three commits separately. Commit 1 (config) is
  the only one needing line-by-line review; commits 2 and 3 are pure reformat —
  confirm `git diff --stat` is whitespace/imports and that the test count and
  build are unchanged, then skim.
- **Rule tuning**: the `select` list is intentionally conservative (`E F W I UP
  B BLE C4 SIM`). Tightening it later (e.g. adding `ANN`, `D`, `RUF`) is a
  separate, opt-in change with its own noise budget — do it incrementally, not
  in this commit.
- **Deferred on purpose**: mypy / type-checking (despite `.mypy_cache/` in
  `.gitignore`) and a frontend test runner. Both are their own plans.
- **CI**: this plan only adds local pre-commit + scripts. Wiring these same
  commands into CI (GitHub Actions) is a follow-up; the commands in the
  "Commands you will need" table are CI-ready as written.
- **Interaction with future work**: any later plan that edits Python/TS must run
  `ruff format` / `prettier` before committing, or pre-commit will reformat
  under it. The line-length choice (`100`) is load-bearing for diff stability —
  changing it later triggers another whole-repo reformat.
