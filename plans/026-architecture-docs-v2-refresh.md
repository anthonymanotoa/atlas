# Plan 026: Make `docs/ARCHITECTURE.md` (and README's frontend line) describe the v2 dashboard that actually exists

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat 0ed8967..HEAD -- docs/ARCHITECTURE.md README.md`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: docs
- **Planned at**: commit `0ed8967`, 2026-07-06

## Why this matters

The repo is **public on GitHub** and `docs/ARCHITECTURE.md` is the document AGENTS.md points
newcomers at for "the full picture". Its Dashboard section still describes the **v1 UI that no
longer exists**: it names a "Radix detail drawer", but the v2 redesign (spec
`docs/superpowers/specs/2026-07-04-atlas-v2-design.md` §4.2) explicitly **replaced the
DetailDrawer with a full `/jobs/:id` page** and re-architected the SPA onto react-router v7 +
TanStack Query with the "Meridian" design system. Anyone (human or agent) reading ARCHITECTURE.md
today builds a wrong mental model of the frontend. This is the same class of "actively wrong
docs" the maintainer already prioritized in plan 022.

## Current state

- `docs/ARCHITECTURE.md` — the stale section, verbatim at `docs/ARCHITECTURE.md:59-63`:

  ```
  ## Dashboard
  FastAPI serves JSON over `localhost` from `atlas.db`; React 19 + Tailwind v4 SPA: action-first
  Needs-Action rail, dnd-kit Kanban, Radix detail drawer (3-state ledger + ready-to-send), cmdk
  palette, funnel + response-rate analytics, aging indicators, downtime banner. UI in Spanish;
  CV/outreach English by default (Spanish optional).
  ```

  What is wrong / missing:
  - "Radix detail drawer" — the drawer was replaced by a **full-page route `/jobs/:id`** (with
    internal tabs) in v2.
  - No mention of **react-router v7 (library mode)** routes, **TanStack Query v5** data hooks,
    or the **Meridian design system v2** (spec source of truth:
    `dashboard/frontend/DESIGN_SYSTEM.md`).
  - No mention of the **intents queue / "Tareas del Brain" panel** (F4 guided handoff), the
    `/followups` and `/upskill` views, or the onboarding wizard — all shipped.

- `README.md:204` — the repo-tree line for the frontend:

  ```
  │   └── frontend/            ←   la interfaz (React + Vite + Tailwind), en español, claro/oscuro
  ```

  Not wrong, but it is the only frontend description in the README and says nothing about the
  router/TanStack architecture or the design system. One line of enrichment is enough here.

- Ground truth to describe (verify by reading, do not guess):
  - `dashboard/frontend/src/routes.tsx` — the actual route table.
  - `dashboard/frontend/src/hooks/` — per-resource TanStack Query hooks (keys in `hooks/keys.ts`).
  - `dashboard/frontend/DESIGN_SYSTEM.md` — Meridian v2 spec (OKLCH tokens, `data-theme`,
    shadcn-style primitives in `src/components/ui/`).
  - `AGENTS.md` sections "Layout" and "Frontend UI / design system" — already accurate for v2;
    ARCHITECTURE.md must not contradict them.
  - Repo language convention: ARCHITECTURE.md is written in English; README.md is in Spanish.
    Match each file's existing language.

## Commands you will need

| Purpose        | Command                                            | Expected on success |
|----------------|----------------------------------------------------|---------------------|
| Python tests   | `uv run pytest`                                    | exit 0, all pass    |
| Full check     | `./scripts/check.sh`                               | exit 0              |
| Route ground truth | `cat dashboard/frontend/src/routes.tsx`        | route list to cite  |

(Docs-only change: running `uv run pytest` once at the end is sufficient; `check.sh` is optional.)

## Scope

**In scope** (the only files you should modify):
- `docs/ARCHITECTURE.md`
- `README.md` (only the frontend tree line at ~204 and, if present, any other sentence that
  contradicts the v2 UI — search before editing)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch, even though they look related):
- `AGENTS.md` — already refreshed for v2 (commit `3cc8595`); leave it alone.
- `dashboard/frontend/DESIGN_SYSTEM.md` — it is the source of truth, not a consumer.
- `docs/superpowers/specs/*` — historical specs, never retro-edited.
- Any code file.

## Git workflow

- Branch: work on the current session branch (repo convention: feature branches merged to
  `master` via PR).
- Commit style: conventional commits, e.g. `docs: describe the v2 dashboard (router/TanStack/Meridian) in ARCHITECTURE.md`
  (match `git log` examples like `docs: refresh AGENTS.md for Meridian v2 (design system + router/TanStack)`).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Rewrite the `## Dashboard` section of `docs/ARCHITECTURE.md`

Open `docs/ARCHITECTURE.md` and replace the section quoted in "Current state" with an accurate
one. It must state, in this order:

1. FastAPI serves JSON over `localhost` from `atlas.db` (unchanged).
2. The SPA is React 19 + Vite + Tailwind v4, routed with **react-router v7 (library mode)**;
   server data flows only through **TanStack Query v5** hooks in `src/hooks/`.
3. The route map — copy the real paths from `dashboard/frontend/src/routes.tsx` (expect
   `/pipeline`, `/jobs/:id` full-page detail with tabs, `/analytics`, `/followups`, `/upskill`,
   `/portfolio`, `/settings`, `/onboarding` — cite what the file actually contains).
4. The UI follows the **Meridian design system v2** (`dashboard/frontend/DESIGN_SYSTEM.md`):
   OKLCH semantic tokens, dark default + light parity via `data-theme`, shadcn-style primitives.
5. Keep the still-true feature notes (Needs-Action rail, dnd-kit kanban, ⌘K palette, analytics,
   Spanish UI) and add the **"Tareas del Brain" intents panel** (guided handoff — the web
   enqueues, the brain executes; see the Intents/brain part of the doc or spec §7.1).
6. Remove the words "detail drawer" entirely.

**Verify**: `grep -in "drawer" docs/ARCHITECTURE.md` → no matches.
**Verify**: `grep -c "Meridian\|TanStack\|react-router" docs/ARCHITECTURE.md` → ≥ 2.

### Step 2: Check the rest of ARCHITECTURE.md for v1-only claims

Read the whole file (it is ~75 lines). If any other sentence contradicts the current code
(e.g. describes `App.tsx` monolith state management, or omits `intents` where it lists DB
tables/flows), fix that sentence minimally in the same style. If the file nowhere mentions the
`intents` table / brain handoff, add 1–2 sentences where the brain or DB is described.

**Verify**: `grep -in "intents" docs/ARCHITECTURE.md` → at least one match.

### Step 3: Enrich the README frontend line

In `README.md` (~line 204), extend the frontend tree line (keep it one line, Spanish) to
mention the router + design system, e.g.:

```
│   └── frontend/            ←   la interfaz (React + Vite + Tailwind, router multi-vista, diseño "Meridian"), en español, claro/oscuro
```

Then search the README for contradictions: `grep -in "drawer\|cajón" README.md` → if matches
describe the old drawer UI, rewrite those sentences to match v2; if no matches, done.

**Verify**: `grep -in "Meridian" README.md` → ≥ 1 match.

### Step 4: Final gate + index row

**Verify**: `uv run pytest` → exit 0 (docs-only change; this proves nothing broke by accident).
**Verify**: `git status --short` → only `docs/ARCHITECTURE.md`, `README.md`, `plans/README.md` modified.
Update this plan's row in `plans/README.md` to DONE with a one-line summary.

## Test plan

No new tests — docs-only. The verification greps above are the machine checks.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -in "drawer" docs/ARCHITECTURE.md` → 0 matches
- [ ] `grep -in "intents" docs/ARCHITECTURE.md` → ≥ 1 match
- [ ] `grep -in "Meridian" README.md` → ≥ 1 match
- [ ] `uv run pytest` exits 0
- [ ] `git status --short` shows only in-scope files modified
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `docs/ARCHITECTURE.md:59-63` does not match the excerpt above (doc drifted since planning).
- `dashboard/frontend/src/routes.tsx` does not exist or contains no route table (frontend
  architecture changed — the plan's ground truth is gone).
- You find yourself wanting to edit `AGENTS.md` or `DESIGN_SYSTEM.md` — out of scope.

## Maintenance notes

- Future UI phases (new routes/views) will re-stale this section; whoever adds a route should
  touch ARCHITECTURE.md in the same PR.
- Reviewer should check the route list against `routes.tsx` — the most likely error is citing
  a route that doesn't exist.
- A fuller ARCHITECTURE.md refresh (engine/brain sections) was considered and deferred: only
  the Dashboard section was actively wrong.
