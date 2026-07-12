# AGENTS.md — working in the Atlas repo

Atlas is a personal, **local, single-user** job-search cockpit. It discovers remote roles,
scores fit, tailors a parse-safe CV per job, drafts outreach, detects referrals, and surfaces
everything in a local dashboard. It runs locally — macOS, or Windows via WSL2 — at **$0** (subscription-funded).
Read `README.md` and `docs/ARCHITECTURE.md` for the full picture.

## Two HARD RULES — never violate

1. **The CV engine never fabricates.** `engine/cv/tailor.py` only reorders/selects the user's
   real data (skills, highlights) and reports keyword coverage. Never add a skill, metric, or
   experience the user did not provide. Any change here must preserve that guarantee.
2. **Atlas sends nothing.** The engine and the `brain` produce *drafts* and a package; the human
   reviews and sends from the dashboard / Gmail drafts. No code path may send, submit, or
   auto-apply. Stay on the user's subscription — never use `claude -p`, the Agent SDK, or an
   `ANTHROPIC_API_KEY` (the `$0` model depends on this; `atlas doctor` enforces it).

## Layout

- `engine/` — deterministic Python, **no LLM**, idempotent: discovery, scoring, CV tailoring/render,
  outreach templating, referrals, SQLite tracker, analytics.
- `brain/` — the daily orchestrator (`run_brain.py` + `SKILL.md`, a Cowork scheduled task).
- `dashboard/backend` — FastAPI serving JSON over `127.0.0.1` (no auth, by design — local single user).
- `dashboard/frontend` — React 19 + Vite + Tailwind v4 SPA, **react-router v7** (library mode) +
  **TanStack Query v5** (per-resource data hooks in `src/hooks/`).
- `config/`, `docs/`, `tests/`, `plans/` (improve-skill audit plans).

## Package managers

- Python: **uv** (`pyproject.toml`, `uv.lock`). Dev tooling is a PEP 735 `[dependency-groups] dev`,
  installed by a plain `uv sync`.
- Frontend: **npm** (`dashboard/frontend/package.json`).

## Verify commands (use these exact forms)

```bash
uv run pytest                                   # Python tests → expect all green
npm --prefix dashboard/frontend run typecheck   # tsc --noEmit
npm --prefix dashboard/frontend run build       # production build
./scripts/check.sh                              # all of the above, one command
```

> A **bare `pytest`** (or anything that resolves a non-project interpreter) will pick up a
> global Python missing `docx`/`rapidfuzz`/`reportlab` and falsely report failures. Always run
> tests through `uv run pytest`.

## Conventions to match

- `from __future__ import annotations`; pydantic v2 models; `@dataclass` result objects.
- typer CLI commands (lazy-import heavy modules inside the command body — intentional).
- `rich.console` for CLI output.
- SQLite: **parameterized** queries only; WAL; UPSERT + `COALESCE` gap-fill; stable 16-char sha1
  natural keys (`normalize.compute_job_id`).
- Tests live in `tests/test_engine.py` (network-free) — model new tests after the existing ones.
- Languages for CVs/outreach are constrained to `{en, es}`.

## Frontend UI / design system

The dashboard follows the **"Meridian" design system (v2)** — spec in
`dashboard/frontend/DESIGN_SYSTEM.md` (aesthetic source of truth:
`docs/superpowers/specs/2026-07-04-atlas-v2-visual-language.md`). It replaces the retired v1
"Warm Editorial": cold slate/ink OKLCH neutrals + a single signal-blue brand accent, with amber
surviving only as the functional `warning` color. **Any UI change must follow it.**

- Compose from the primitives in `dashboard/frontend/src/components/ui/*` (shadcn-style: Radix +
  cva + `cn` from `@/lib/utils`). Don't hand-roll buttons/inputs/badges or hardcode colors.
- Use the semantic tokens / Tailwind utilities (`bg-card`, `text-muted-foreground`, `bg-primary`,
  `bg-secondary`, `border-border`, `ring-ring`, `bg-sidebar`, …) from `src/index.css`. **Never** use
  `bg-accent`/`bg-muted` (unmapped on purpose) — use `secondary`. Theme is `data-theme` on `<html>`
  (never `.dark`); default is dark, with full light parity.
- Icons come from `src/components/ui/icons.ts` (lucide) — **no raw emoji**. Fonts are Space Grotesk
  (sans) + JetBrains Mono; use `tabular-nums` on live numbers.
- Pages route via **react-router v7** (`src/routes.tsx`, `AppShell.tsx`) and read server data only
  through **TanStack Query** hooks in `src/hooks/` (keys in `src/hooks/keys.ts`) — never `api.*` or
  `useEffect`+`useState` for server data. Every page uses `LoadingState`/`ErrorState`/`EmptyState`
  from `src/components/ui/states.tsx`.
- `components.json` enables the shadcn CLI/skill; a repo skill `.claude/skills/atlas-design-system/`
  auto-enforces this. FE lint is `--max-warnings 0`; the production build
  (`npm --prefix dashboard/frontend run build`) runs as the last step of `check.sh`.

## Knowledge graph (graphify)

This repo has a graphify knowledge graph (god nodes, community structure, cross-file edges).
The `graphify-out/` artifact is **gitignored** — rebuild it locally with `/graphify .`.

- **Codebase questions:** when `graphify-out/graph.json` exists, run `graphify query "<question>"`
  first — it returns a scoped subgraph, usually much smaller than grep or `GRAPH_REPORT.md`. Use
  `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for one node.
  The `.claude/settings.json` `PreToolUse` hooks nudge this automatically before grep/read.
- **After changing code:** the graph auto-refreshes at the end of each Claude turn that edited a
  file — a `Stop` hook in `.claude/settings.json` runs `graphify update .` (AST-only, **no LLM, no
  API cost**, ~1s), so it stays within the $0 hard rule. To refresh by hand: `graphify update .`
  (code only). **Doc/markdown changes are NOT picked up by the auto-update** — run a full
  `/graphify .` occasionally for those (uses the Claude session as backend, never an
  `ANTHROPIC_API_KEY`).
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review.
