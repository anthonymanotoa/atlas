# Plan 023: Make `./scripts/check.sh` a complete gate — add the frontend production build

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 413ae10..HEAD -- scripts/check.sh AGENTS.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (touches `AGENTS.md` lines 69-70 only; plan 022 touches line 36 — disjoint, either order works)
- **Category**: dx
- **Planned at**: commit `413ae10`, 2026-07-06

## Why this matters

`./scripts/check.sh` is documented as the repo's one-command "is the repo green?" gate,
but it does not run the frontend **production build**. `tsc --noEmit` (the typecheck
step) does not catch everything the bundler does — dead/missing asset imports, Vite
config issues, CSS/Tailwind pipeline errors. Today a developer can pass the whole gate
and still have a broken `npm run build`, which is exactly what `scripts/run.sh` needs to
serve the dashboard. One added line closes the gap; AGENTS.md then stops documenting the
hole as a caveat.

## Current state

`scripts/check.sh:19-26` — the frontend section ends at tests; no build:

```bash
echo "==> Frontend: install"
npm --prefix dashboard/frontend install

echo "==> Frontend: lint + format check + typecheck + tests"
npm --prefix dashboard/frontend run lint
npm --prefix dashboard/frontend run format:check
npm --prefix dashboard/frontend run typecheck
npm --prefix dashboard/frontend test
```

`AGENTS.md:69-70` documents the gap as a caveat:

```
`components.json` enables the shadcn CLI/skill; a repo skill `.claude/skills/atlas-design-system/`
auto-enforces this. FE lint is `--max-warnings 0`; run `npm --prefix dashboard/frontend run build`
(it is **not** part of `check.sh`).
```

Convention to match: `check.sh` uses `echo "==> <Stack>: <what>"` step banners and
relies on `set -euo pipefail` (line 5) for fail-fast — no `if` wrappers.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| FE build alone | `npm --prefix dashboard/frontend run build` | exit 0, `dist/` written |
| Full gate | `./scripts/check.sh` | ends with `✓ All checks passed.` |

## Scope

**In scope** (the only files you should modify):

- `scripts/check.sh`
- `AGENTS.md` (lines 69-70 sentence only)

**Out of scope** (do NOT touch):

- `dashboard/frontend/package.json` — the `build` script already exists; don't alter it.
- `scripts/run.sh` — it builds on demand for serving; unrelated.
- `AGENTS.md:36` (test-count line) — owned by plan 022.

## Git workflow

- Branch: `advisor/023-checksh-frontend-build`.
- One commit: `dx(check): include the frontend production build in the one-command gate`.
- Never `git add .` — add the two files by name.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the build step to check.sh

Append after the `npm --prefix dashboard/frontend test` line (`scripts/check.sh:26`),
matching the banner style:

```bash
echo "==> Frontend: production build"
npm --prefix dashboard/frontend run build
```

**Verify**: `./scripts/check.sh` → runs through the new step and ends with
`✓ All checks passed.`

### Step 2: Update the AGENTS.md caveat

Rewrite the sentence at `AGENTS.md:69-70` so it reads (keep the surrounding lines):

```
auto-enforces this. FE lint is `--max-warnings 0`; the production build
(`npm --prefix dashboard/frontend run build`) runs as the last step of `check.sh`.
```

**Verify**: `grep -n "not.*part of.*check.sh" AGENTS.md` → no matches.

## Test plan

No unit tests — the gate itself is the test: `./scripts/check.sh` must pass end-to-end
including the new build step.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n "run build" scripts/check.sh` → one match
- [ ] `./scripts/check.sh` exits 0 and prints the new `==> Frontend: production build` banner
- [ ] `grep -n "not.*part of.*check.sh" AGENTS.md` → no matches
- [ ] Only the two in-scope files are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `npm --prefix dashboard/frontend run build` fails on the CURRENT code before your
  change — that's a pre-existing break this plan must not paper over; report it.
- `check.sh` has drifted from the excerpt (someone already added a build step).

## Maintenance notes

- The build adds ~10-20s to a full check; if that ever becomes a complaint, the right
  split is a `--fast` flag, not removing the step.
- If a CI workflow is ever added, it should call `./scripts/check.sh` so the local and
  CI gates can't drift apart.
