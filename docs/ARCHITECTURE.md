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

**CV↔JD match score (`engine/cv/match.py`).** A visible **0–100** = importance-weighted
coverage of a posting's JD keywords by the master CV, plus the importance-ranked **missing**
keywords (honest gaps, never faked). Distinct from `fit_score` (job vs. your *criteria*): this
is CV vs. the *job description*. Computed cheaply per job in `scoring/run.py` (no DOCX render),
persisted on `jobs.match_score` / `jobs.match_missing`, and shown as a "match %" chip on the
board + a gaps panel in the drawer. Reuses the same gazetteer + truthful coverage predicate as
the tailor, so the two stay consistent.

**Importing an existing CV (`engine/cv/import_cv.py`, `atlas import-cv`).** Two-step and
conservative: the engine **deterministically extracts text** from a PDF (`pdfplumber`) or DOCX
(`python-docx`) into a `master_cv.draft.yaml` scaffold; the human + Cowork then map it into the
schema truthfully and save it themselves. It **never** writes `master_cv.yaml` directly and
never structures/invents — CV layouts vary too much for a reliable deterministic parser.

## Interview prep (`engine/interview/interview_prep.py`)
Deterministic prep-doc per interview: likely behavioral + role/technical questions, company
learnings, and a STAR evidence bank grounded **only** in real CV highlights. The "topics to
review" section is derived from *this* posting via the CV↔JD match (`match.py`) — the JD
keywords your CV doesn't yet evidence — so it's specific, not a fixed taxonomy, and degrades to
nothing when no keywords map. Interviewer research stays supervised (Claude-in-Chrome).

## Dashboard
FastAPI serves JSON over `localhost` from `atlas.db`; React 19 + Tailwind v4 SPA: action-first
Needs-Action rail, dnd-kit Kanban, Radix detail drawer (3-state ledger + ready-to-send), cmdk
palette, funnel + response-rate analytics, aging indicators, downtime banner. UI in Spanish;
CV/outreach English by default (Spanish optional).

## Deferred: MCP server (design note, not built)
A thin **Atlas-as-MCP-server** (FastMCP) would wrap the existing engine functions
(`discover` / `score` / `tailor` / `interview` / `top`) so you can drive Atlas conversationally
from Claude. It runs local and keeps the **$0** model (Claude is the subscription client; the
engine is deterministic Python). Deferred because it overlaps the existing CLI + `brain/SKILL.md`
path and adds a dependency. Consuming `stickerdaniel/linkedin-mcp` (logged-in session) is a
possible *external, optional* tool only — **not packaged** — given LinkedIn ToS/ban risk; see
`docs/RATE_LIMITING.md` for the supervised-browser guardrails.
