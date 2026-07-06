# Plan 022: Fix actively-wrong docs — public-repo claim, stale test counts, stale dev-deps note

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 413ae10..HEAD -- README.md AGENTS.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (touches `AGENTS.md` line 36 only; plan 023 touches lines 69-70 — disjoint, either order works)
- **Category**: docs
- **Planned at**: commit `413ae10`, 2026-07-06

## Why this matters

Three documented claims are now false, and one of them is a **privacy claim**: the
README tells users the repository is *private* when it went **public on 2026-06-24**.
Someone reading section 8 could reasonably conclude that committing personal data is
harmless ("nadie más lo ve") — exactly the wrong conclusion for a public repo whose
protection is the `.gitignore`, not visibility. The other two stale claims (test count
"19 passed" vs. the real 180; a `uv sync --extra dev` instruction that contradicts the
current PEP 735 dependency-groups setup) make agents and humans distrust the docs or run
the wrong command. Stale docs that are actively wrong are worse than missing docs.

## Current state

- `README.md` — Spanish, user-facing project doc.
- `AGENTS.md` — agent-facing working guide; its "Verify commands" block is quoted by
  agents on every session.
- `plans/README.md` — the improve-skill plan index; its header states the verification
  baseline.

Excerpts as they exist today:

`README.md:314-315` (end of section 8, "Tus datos y tu privacidad"):

```
cualquier `.env`. Cada perfil queda **aislado** en su propia carpeta. El repositorio es
**privado**.
```

The repo is public since 2026-06-24 (GitHub `anthonymanotoa/atlas`, master protected).

`README.md:303-304` (the test-command note in section 7):

```
> Si las pruebas se quejan de paquetes faltantes (docx, rapidfuzz, pytest), corre
> `uv sync --extra dev` antes. `uv sync` a secas poda pytest — es un detalle conocido.
```

This is stale: `pyproject.toml:27-28` moved dev tooling to a PEP 735 dependency group
(`[dependency-groups] dev = [...]`) precisely so a **plain `uv sync` installs it by
default** (that's the comment in `pyproject.toml:25-26`). There is no `--extra dev`
anymore, and `uv sync` does NOT prune pytest.

`AGENTS.md:36` (inside the "Verify commands" fenced block):

```
uv run pytest                                   # Python tests → expect "19 passed"
```

The suite is at **180 passed** as of `413ae10` (verified 2026-07-06 with `uv run pytest`).

(The `plans/README.md` verification header had the same staleness; the advisor already
fixed it during the 2026-07-06 index reconciliation — it is NOT in this plan's scope.)

Conventions to match: README is written in Spanish, second person ("tu Mac", "tú
decides"); AGENTS.md is terse English. Keep each file's language and voice.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Confirm current test count | `uv run pytest` | `N passed` — use the N you observe |
| Confirm dev group installs | `uv sync && uv run pytest -q` | tests run (pytest present) |
| Lint (README untouched by it, sanity only) | `uv run ruff check .` | exit 0 |

## Scope

**In scope** (the only files you should modify):

- `README.md` (two spots: lines ~303-304 and ~314-315)
- `AGENTS.md` (line 36 only)
- `plans/README.md` (your status row only, at the end)

**Out of scope** (do NOT touch):

- `AGENTS.md:69-70` (the "build is not part of check.sh" sentence) — owned by plan 023.
- The individual historical plan files `plans/001-020-*.md` — they are point-in-time
  documents; their internal "9 passed"/"19 passed" baselines are historical record, not
  live instructions. Do not rewrite history.
- `docs/SETUP.md`, `docs/SECURITY.md` — not audited as stale; leave them.

## Git workflow

- Branch: `advisor/022-docs-truth-pass`.
- One commit, conventional style: `docs: repo is public + refresh stale test-count/dev-deps notes`.
- Never `git add .` — add the three files by name.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Fix the privacy claim in README section 8

Replace the sentence at `README.md:314-315` so the paragraph ends:

```
cualquier `.env`. Cada perfil queda **aislado** en su propia carpeta. El repositorio en
GitHub es **público**, así que la protección de tus datos es exactamente esa lista del
`.gitignore`: lo personal vive solo en tu Mac y **nunca** debe commitearse.
```

**Verify**: `grep -n "privado" README.md` → no match in section 8 (a match elsewhere,
if any, must not claim the repo is private).

### Step 2: Fix the dev-deps note in README section 7

Replace the note at `README.md:303-304` with:

```
> Si las pruebas se quejan de paquetes faltantes (docx, rapidfuzz, pytest), corre
> `uv sync` antes: instala también el grupo `dev` (pytest, ruff) por defecto.
```

**Verify**: `grep -n "extra dev" README.md` → no matches.

### Step 3: Fix the expected test count in AGENTS.md

Update `AGENTS.md:36` to the count you observed in "Commands you will need" (180 at
planning time), e.g.:

```
uv run pytest                                   # Python tests → expect "180 passed" (count grows; all green is the bar)
```

**Verify**: `grep -n "19 passed" AGENTS.md` → no matches.

## Test plan

No code changes — no new tests. The verification greps above are the gate.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -rn "El repositorio es" README.md` shows the public-repo wording
- [ ] `grep -n "extra dev" README.md` → no matches
- [ ] `grep -n "19 passed" AGENTS.md` → no matches
- [ ] `uv run pytest` exits 0 (nothing broken by doc edits — sanity)
- [ ] Only `README.md`, `AGENTS.md` and the `plans/README.md` status row are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- Any excerpt in "Current state" no longer matches the live file (drift — e.g. someone
  already fixed the privacy sentence).
- You find the repo is actually private (`gh repo view --json visibility`) — the whole
  premise of Step 1 would be wrong; report instead of editing.
- You feel the urge to fix OTHER stale-looking docs while in there (SETUP.md etc.) —
  out of scope; list them in your report instead.

## Maintenance notes

- The test count in AGENTS.md will drift again as the suite grows; the suggested
  wording ("count grows; all green is the bar") makes the next drift harmless.
- If the repo's visibility ever changes again, README section 8 is the single place
  that states it.
