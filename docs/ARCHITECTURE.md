# Atlas — architecture

## Three surfaces
- **Claude Code (interactive)** — builds/maintains the machinery. Subscription.
- **Cowork scheduled task (`brain/SKILL.md`, daily)** — thin orchestrator that runs the engine,
  optionally sharpens drafts, creates Gmail *drafts*. Subscription. **Sends nothing.**
- **Claude in Chrome** — supervised hands on LinkedIn + company forms (your session). You submit.

## Deterministic vs LLM
- **`engine/` (Python, no LLM, idempotent):** discovery, dedupe, DB, fit scoring, JD keyword
  extraction, CV render + parse-check, outreach templating, referral match, follow-up schedule.
- **LLM (inside the Cowork run):** nuanced ranking, truthful CV/message wording, why-fit. The
  engine always produces a working baseline, so the tool degrades gracefully without the LLM.

## Data model (SQLite, WAL)
`jobs` (natural-key `id` = sha1 of normalized company+title+location, UNIQUE → cross-source
dedupe via UPSERT; per-stage timestamp columns; state machine), `cv_versions`, `messages`,
`contacts`, `applications`, `followups`, `events`, `source_health`, `meta` (watermark +
`last_success_ts` heartbeat).

State machine: `discovered → scored → shortlisted → tailored → drafted → ready → applied →
responded → interview → offer / rejected / closed`. Re-runs/catch-ups never duplicate (UPSERT +
"only act on rows with null artifacts"); rescore never regresses an advanced job.

## Discovery sources
Spine: **Greenhouse / Lever / Ashby / SmartRecruiters** keyless JSON (per-company registry) +
**Indeed** (JobSpy). Secondary: **LinkedIn guest** (no login → account-safe; capped ~200/run to
stay under the IP rate-limit wall; no proxies). Baseline: **Himalayas** (remote-first) + **Adzuna**
(optional free keys). Google/ZipRecruiter excluded (broken in 2026); per-source try/except +
`source_health` so silent breakage surfaces.

## CV tailoring
Two stages: (1) **parse-safety** — single column, standard headings, Month-YYYY dates, DOCX,
no tables/graphics; verified by re-parsing the output. (2) **keyword tailoring** — ontology
gazetteer match, exact-title injection, dual-form acronyms, anti-stuffing (≤18 skills), a
transparent coverage report. **Never fabricates** — only reorders/selects the user's real data.

## Dashboard
FastAPI serves JSON over `localhost` from `atlas.db`; React 19 + Tailwind v4 SPA: action-first
Needs-Action rail, dnd-kit Kanban, Radix detail drawer (3-state ledger + ready-to-send), cmdk
palette, funnel + response-rate analytics, aging indicators, downtime banner. UI in Spanish;
CV/outreach English by default (Spanish optional).
